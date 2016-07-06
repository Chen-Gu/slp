#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;

	// The distance between this node and each source
	uses interface Dictionary<am_addr_t, uint16_t> as SourceDistances;

	// The distance between the recorded source and the sink
	uses interface Dictionary<am_addr_t, uint16_t> as SinkSourceDistances;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, PermFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string(void)
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		case TempFakeNode:			return "TempFakeNode";
		case PermFakeNode:			return "PermFakeNode";
		default:					return "<unknown> ";
		}
	}

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;


	int16_t min_sink_source_distance = BOTTOM;
	int16_t min_source_distance = BOTTOM;
	int16_t sink_distance = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;
	bool is_pfs_candidate = FALSE;

	uint16_t first_source_distance = 0;
	bool first_source_distance_set = FALSE;

	uint32_t extra_to_send = 0;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm = UnknownAlgorithm;

	// Produces a random float between 0 and 1
	float random_float()
	{
		// There appears to be problem with the 32 bit random number generator
		// in TinyOS that means it will not generate numbers in the full range
		// that a 32 bit integer can hold. So use the 16 bit value instead.
		// With the 16 bit integer we get better float values to compared to the
		// fake source probability.
		// Ref: https://github.com/tinyos/tinyos-main/issues/248
		const uint16_t rnd = call Random.rand16();

		return ((float)rnd) / UINT16_MAX;
	}

	uint32_t get_away_delay(void)
	{
		//assert(SOURCE_PERIOD_MS != BOTTOM);

		return SOURCE_PERIOD_MS / 2;
	}

	uint16_t estimated_number_of_sources(void)
	{
		return max(1, call SourceDistances.count());
	}

	int32_t ignore_choose_distance(int32_t distance)
	{
		// We contemplated changing this versus the original algorithm,
		// but decided against it.
		// By randomising this, the capture rates for the Sink Corner
		// are very bad.
		//return (int32_t)ceil(distance * random_float());
		return distance;
	}

	bool should_process_choose(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return !(min_sink_source_distance != BOTTOM &&
				min_source_distance <= ignore_choose_distance((4 * min_sink_source_distance) / 5));

		case FurtherAlgorithm:
			return !seen_pfs && !(min_sink_source_distance != BOTTOM &&
				min_source_distance <= ignore_choose_distance(((1 * min_sink_source_distance) / 2) - 1));

		default:
			return TRUE;
		}
	}

	bool pfs_can_become_normal(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return TRUE;

		case FurtherAlgorithm:
			return FALSE;

		default:
			return FALSE;
		}
	}

#if defined(PB_SINK_APPROACH)
	uint32_t get_dist_to_pull_back(void)
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			// When reasoning we want to pull back in terms of the sink distance.
			// However, the Dsrc - the Dss gives a good approximation of the Dsink.
			// It has the added benefit that this is only true when the TFS is further from
			// the source than the sink is.
			// This means that TFSs near the source will send fewer messages.
			if (min_source_distance == BOTTOM || min_sink_source_distance == BOTTOM)
			{
				distance = sink_distance;
			}
			else
			{
				distance = min_source_distance - min_sink_source_distance;
			}
			break;

		default:
		case FurtherAlgorithm:
			distance = max(min_sink_source_distance, sink_distance);
			break;
		}

		distance = max(distance, 1);
		
		return distance;	
	}

#elif defined(PB_ATTACKER_EST_APPROACH)
	uint32_t get_dist_to_pull_back(void)
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			distance = sink_distance + sink_distance;
			break;

		default:
		case FurtherAlgorithm:
			distance = max(min_sink_source_distance, sink_distance);
			break;
		}

		distance = max(distance, 1);
		
		return distance;
	}

#else
#	error "Technique not specified"
#endif

	uint16_t get_tfs_num_msg_to_send(void)
	{
		const uint16_t distance = get_dist_to_pull_back();
		const uint16_t est_num_sources = estimated_number_of_sources();

		simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
			distance, source_distance, sink_distance, min_sink_source_distance);

		return distance * est_num_sources;
	}

	uint32_t get_tfs_duration(void)
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance <= 1)
		{
			duration -= get_away_delay();
		}

		simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		simdbgverbose("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		const double x = seq_inc / (double)counter;

		const uint32_t result_period = ceil(SOURCE_PERIOD_MS * x);

		simdbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, x);

		return result_period;
	}

	void update_source_distance(const NormalMessage* rcvd)
	{
		const uint16_t* distance = call SourceDistances.get(rcvd->source_id);
		const uint16_t* sink_source_distance = call SinkSourceDistances.get(rcvd->source_id);

		if (distance == NULL)
		{
			call SourceDistances.put(rcvd->source_id, rcvd->source_distance + 1);
		}
		else
		{
			call SourceDistances.put(rcvd->source_id, min(*distance, rcvd->source_distance + 1));
		}

		if (min_source_distance == BOTTOM || min_source_distance > rcvd->source_distance + 1)
		{
			min_source_distance = rcvd->source_distance + 1;
		}
		
		/*if (rcvd->sink_distance != BOTTOM)
		{
			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->sink_distance + 1);

			if (sink_source_distance == NULL)
			{
				//simdbg("stdout", "Updating sink distance of %u to %d\n", rcvd->source_id, rcvd->sink_distance);
				call SinkSourceDistances.put(rcvd->source_id, rcvd->sink_distance);
			}
			else
			{
				call SinkSourceDistances.put(rcvd->source_id, min(*sink_source_distance, rcvd->sink_distance));
			}
		}*/
	}

	void stop_pfs_candidate(uint16_t max_hop)
	{
		// TODO: "max_hop != UINT16_MAX" is a hack, find out where UINT16_MAX comes from and fix it!

		if (is_pfs_candidate && (!first_source_distance_set || (max_hop != UINT16_MAX && max_hop > first_source_distance + 1)))
		{
			//simdbg("stdout", "%s is no longer a PFS candidate as !first_source_distance_set=%d || %u > %u\n",
			//	type_to_string(), !first_source_distance_set, max_hop, first_source_distance + 1);

			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}
	}

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);

	void become_Normal(void)
	{
		type = NormalNode;

		call FakeMessageGenerator.stop();

		simdbg("Fake-Notification", "The node has become a Normal\n");
	}

	void become_Fake(const AwayChooseMessage* message, NodeType perm_type)
	{
		if (perm_type != PermFakeNode && perm_type != TempFakeNode)
		{
			assert("The perm type is not correct");
		}

		type = perm_type;

		if (type == PermFakeNode)
		{
			simdbg("Fake-Notification", "The node has become a PFS\n");

			call FakeMessageGenerator.start(message);
		}
		else
		{
			simdbg("Fake-Notification", "The node has become a TFS\n");

			call FakeMessageGenerator.startLimited(message, get_tfs_duration());
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.max_hop = first_source_distance;
		message.min_sink_source_distance = min_sink_source_distance;

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		message.min_sink_source_distance = min_sink_source_distance;
		message.max_hop = min_sink_source_distance;
		message.algorithm = ALGORITHM;

		sequence_number_increment(&away_sequence_counter);

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sink_sent_away = TRUE;
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		stop_pfs_candidate(rcvd->max_hop);

		update_source_distance(rcvd);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				is_pfs_candidate = TRUE;
				first_source_distance_set = TRUE;
				call Leds.led1On();
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_source_distance(rcvd);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!sink_sent_away)
			{
				call AwaySenderTimer.startOneShot(get_away_delay());
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_source_distance(rcvd);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receive_Normal(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		stop_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: //Normal_receive_Away(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Normal_receive_Away(rcvd, source_addr); break;
		case SinkNode: break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		stop_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

#ifdef SLP_VERBOSE_DEBUG
		if (!should_process_choose())
		{
			simdbgverbose("slp-debug", "Dropping choose and not becoming FS because of should_process_choose() (dss=%d, ds=%d)\n",
				min_sink_source_distance, min_source_distance);
		}
#endif

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			if (is_pfs_candidate)
			{
				become_Fake(rcvd, PermFakeNode);
			}
			else
			{
				become_Fake(rcvd, TempFakeNode);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
		case SinkNode: break;
		case TempFakeNode: break;
		case PermFakeNode: break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			message.min_sink_source_distance = min_sink_source_distance;

			send_Fake_message(&message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);
			source_fake_sequence_increments += 1;

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		stop_pfs_candidate(rcvd->max_hop);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		stop_pfs_candidate(rcvd->max_hop);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (pfs_can_become_normal() &&
				type == PermFakeNode &&
				rcvd->from_pfs &&
				(
					(rcvd->source_distance > min_source_distance) ||
					(rcvd->source_distance == min_source_distance && sink_distance < rcvd->sink_distance) ||
					(rcvd->source_distance == min_source_distance && sink_distance == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		if (type == PermFakeNode)
		{
			return get_pfs_period();
		}
		else if (type == TempFakeNode)
		{
			return get_tfs_period();
		}
		else
		{
			simdbgerror("stdout", "Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->min_sink_source_distance = min_sink_source_distance;
		message->source_distance = min_source_distance;
		message->max_hop = first_source_distance;
		message->sink_distance = sink_distance;
		message->from_pfs = (type == PermFakeNode);
		message->source_id = TOS_NODE_ID;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;

		simdbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		message.min_sink_source_distance = min_sink_source_distance;
		message.sink_distance += 1;

		// TODO: repeat 3
		extra_to_send = 2;
		send_Choose_message(&message, AM_BROADCAST_ADDR);

		become_Normal();
	}

	event void FakeMessageGenerator.sent(error_t error, const FakeMessage* tosend)
	{
		const char* result;

		// Only if the message was successfully broadcasted, should the seqno be incremented.
		if (error == SUCCESS)
		{
			sequence_number_increment(&fake_sequence_counter);
		}

		simdbgverbose("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);

		switch (error)
		{
		case SUCCESS: result = "success"; break;
		case EBUSY: result = "busy"; break;
		default: result = "failed"; break;
		}

		if (tosend != NULL)
		{
			METRIC_BCAST(Fake, result, tosend->sequence_number);
		}
		else
		{
			METRIC_BCAST(Fake, result, BOTTOM);
		}

		if (pfs_can_become_normal())
		{
			if (type == PermFakeNode && !is_pfs_candidate)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}
}