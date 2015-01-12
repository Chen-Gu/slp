#include "AwayChooseMessage.h"
#include "Constants.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "SequenceNumber.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#ifdef SLP_VERBOSE_DEBUG
#	define dbgverbose(...) dbg(__VA_ARGS__)
#else
#	define dbgverbose(...)
#endif

#define max(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   _a < _b ? _a : _b; })

#define minbot(a, b) \
	({ __typeof__(a) _a = (a), _b = (b); \
	   (_a == BOTTOM || _b < _a) ? _b : _a; })


#define SEND_MESSAGE(NAME) \
bool send_##NAME##_message(const NAME##Message* tosend) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
 		void const* void_message = call Packet.getPayload(&packet, sizeof(NAME##Message)); \
 		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string()); \
			return FALSE; \
		} \
 \
 		if (tosend != NULL) \
 		{ \
			*message = *tosend; \
		} \
		else \
		{ \
			/* Need tosend set, so that the metrics recording works. */ \
			tosend = message; \
		} \
 \
		status = call NAME##Send.send(AM_BROADCAST_ADDR, &packet, sizeof(NAME##Message)); \
		if (status == SUCCESS) \
		{ \
			call Leds.led0On(); \
			busy = TRUE; \
 \
			METRIC_BCAST(NAME, "success"); \
 \
			return TRUE; \
		} \
		else \
		{ \
			METRIC_BCAST(NAME, "failed"); \
 \
			return FALSE; \
		} \
	} \
	else \
	{ \
		dbgverbose("SourceBroadcasterC", "%s: Broadcast" #NAME "Timer busy, not sending " #NAME " message.\n", sim_time_string()); \
 \
		METRIC_BCAST(NAME, "busy"); \
 \
		return FALSE; \
	} \
}

#define SEND_DONE(NAME) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	dbgverbose("SourceBroadcasterC", "%s: " #NAME "Send sendDone with status %i.\n", sim_time_string(), error); \
 \
	if (&packet == msg) \
	{ \
		if (extra_to_send > 0) \
		{ \
			if (send_##NAME##_message(NULL)) \
			{ \
				--extra_to_send; \
			} \
			else \
			{ \
				call Leds.led0Off(); \
				busy = FALSE; \
			} \
		} \
		else \
		{ \
			call Leds.led0Off(); \
			busy = FALSE; \
		} \
	} \
}

#define RECEIVE_MESSAGE_BEGIN(NAME) \
event message_t* NAME##Receive.receive(message_t* msg, void* payload, uint8_t len) \
{ \
	const NAME##Message* const rcvd = (const NAME##Message*)payload; \
 \
	const am_addr_t source_addr = call AMPacket.source(msg); \
 \
	dbg_clear("Attacker-RCV", "%" PRIu64 ",%u,%u,%u,%u\n", sim_time(), #NAME, TOS_NODE_ID, source_addr, rcvd->sequence_number); \
 \
	if (len != sizeof(NAME##Message)) \
	{ \
		dbgerror("SourceBroadcasterC", "%s: Received " #NAME " of invalid length %hhu.\n", sim_time_string(), len); \
		return msg; \
	} \
 \
	dbgverbose("SourceBroadcasterC", "%s: Received valid " #NAME ".\n", sim_time_string()); \
 \
	switch (type) \
	{

#define RECEIVE_MESSAGE_END(NAME) \
		default: \
		{ \
			dbgerror("SourceBroadcasterC", "%s: Unknown node type %s. Cannot process " #NAME " message\n", sim_time_string(), type_to_string()); \
		} break; \
	} \
 \
	return msg; \
}

#define METRIC_RCV(TYPE, DISTANCE) \
	dbg_clear("Metric-RCV", "%s,%" PRIu64 ",%u,%u,%u,%u\n", #TYPE, sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS) \
	dbg_clear("Metric-BCAST", "%s,%" PRIu64 ",%u,%s,%u\n", #TYPE, sim_time(), TOS_NODE_ID, STATUS, (tosend != NULL) ? tosend->sequence_number : (uint32_t)-1)

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
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, PermFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
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

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	int32_t sink_source_distance = BOTTOM;
	int32_t source_distance = BOTTOM;
	int32_t sink_distance = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;
	bool is_pfs_candidate = FALSE;

	uint32_t first_source_distance = 0;
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

	int32_t ignore_choose_distance(int32_t distance)
	{
		// We contemplated changing this versus the original algorithm,
		// but decided against it.
		// By randomising this, the capture rates for the Sink Corner
		// are very bad.
		//return (int32_t)ceil(distance * random_float());
		return distance;
	}

	bool should_process_choose()
	{
		switch (algorithm)
		{
			case GenericAlgorithm:
				return !(sink_source_distance != BOTTOM &&
					source_distance <= ignore_choose_distance((3 * sink_source_distance) / 4));

			case FurtherAlgorithm:
				return !seen_pfs && !(sink_source_distance != BOTTOM &&
					source_distance <= ignore_choose_distance(((1 * sink_source_distance) / 2) - 1));

			default:
				return TRUE;
		}
	}

	bool pfs_can_become_normal()
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

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		if (TOS_NODE_ID == SOURCE_NODE_ID)
		{
			type = SourceNode;
		}
		else if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			if (type == SourceNode)
			{
				call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);
			}
		}
		else
		{
			dbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		dbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	SEND_MESSAGE(Normal);
	SEND_MESSAGE(Away);
	SEND_MESSAGE(Choose);
	SEND_MESSAGE(Fake);

	SEND_DONE(Normal);
	SEND_DONE(Away);
	SEND_DONE(Choose);
	SEND_DONE(Fake);

	void become_Normal()
	{
		type = NormalNode;

		call FakeMessageGenerator.stop();

		dbg("Fake-Notification", "The node has become a Normal\n");
	}

	void become_Fake(const AwayChooseMessage* message, NodeType perm_type)
	{
		float rndFloat;

		if (perm_type != PermFakeNode && perm_type != TempFakeNode)
		{
			assert("The perm type is not correct");
		}

		type = perm_type;

		rndFloat = random_float();

		if (type == PermFakeNode)
		{
			if (rndFloat <= PR_PFS)
			{
				dbg("Fake-Notification", "The node has become a PFS\n");

				dbgverbose("Fake-Probability-Decision",
 					"The node %u has become a PFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_PFS, rndFloat);

				call FakeMessageGenerator.start(message, FAKE_PERIOD_MS);
			}
			else
			{
 				dbgverbose("Fake-Probability-Decision",
 					"The node %u has not become a PFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_PFS, rndFloat);
			}
		}
		else
		{
			if (rndFloat <= PR_TFS)
			{
				dbg("Fake-Notification", "The node has become a TFS\n");

				dbgverbose("Fake-Probability-Decision",
					"The node %u has become a TFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_TFS, rndFloat);

				call FakeMessageGenerator.startLimited(message, FAKE_PERIOD_MS, TEMP_FAKE_DURATION_MS);
			}
			else
			{
				dbgverbose("Fake-Probability-Decision",
					"The node %u has not become a TFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_TFS, rndFloat);
			}
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.max_hop = first_source_distance;
		message.source_id = TOS_NODE_ID;
		message.sink_source_distance = sink_source_distance;

		if (send_Normal_message(&message))
		{
			sequence_number_increment(&normal_sequence_counter);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.sink_distance = 0;
		message.sink_source_distance = sink_source_distance;
		message.max_hop = sink_source_distance;
		message.algorithm = ALGORITHM;

		sequence_number_increment(&away_sequence_counter);

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message))
		{
			sink_sent_away = TRUE;
		}
	}

	void Normal_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			dbgverbose("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), rcvd->sequence_number, source_addr);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				is_pfs_candidate = TRUE;
				first_source_distance_set = TRUE;
				call Leds.led1On();
			}

			source_distance = minbot(source_distance, rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			send_Normal_message(&forwarding_message);
		}
	}

	void Sink_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			sink_source_distance = minbot(sink_source_distance, rcvd->source_distance + 1);

			if (!sink_sent_away)
			{
				call AwaySenderTimer.startOneShot(SOURCE_PERIOD_MS / 2);
			}
		}
	}

	void Fake_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			send_Normal_message(&forwarding_message);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
		case SinkNode: Sink_receieve_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receieve_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receieve_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1);

			sink_source_distance = minbot(sink_source_distance, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message);
		}
	}

	void Normal_receieve_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away)
		case SourceNode: Source_receieve_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Away(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receieve_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Choose, rcvd->sink_distance + 1);

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

	RECEIVE_MESSAGE_BEGIN(Choose)
		case NormalNode: Normal_receieve_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			message.sink_source_distance = sink_source_distance;

			send_Fake_message(&message);
		}
	}

	void Source_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;
		}
	}

	void Normal_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message);
		}
	}

	void Fake_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message);

			if (pfs_can_become_normal() &&
				type == PermFakeNode &&
				rcvd->from_pfs &&
				(
					(rcvd->source_distance > source_distance) ||
					(rcvd->source_distance == source_distance && sink_distance < rcvd->sink_distance) ||
					(rcvd->source_distance == source_distance && sink_distance == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake)
		case SinkNode: Sink_receieve_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receieve_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receieve_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->sink_source_distance = sink_source_distance;
		message->source_distance = source_distance;
		message->max_hop = first_source_distance;
		message->sink_distance = sink_distance;
		message->from_pfs = (type == PermFakeNode);
		message->source_id = TOS_NODE_ID;

		sequence_number_increment(&fake_sequence_counter);
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;

		dbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		message.sink_source_distance = sink_source_distance;
		message.sink_distance += 1;

		// TODO: repeat 3
		extra_to_send = 2;
		send_Choose_message(&message);

		become_Normal();
	}

	event void FakeMessageGenerator.sent(error_t error, const FakeMessage* tosend)
	{
		const char* result;

		dbgverbose("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);

		switch (error)
		{
		case SUCCESS: result = "success"; break;
		case EBUSY: result = "busy"; break;
		default: result = "failed"; break;
		}

		METRIC_BCAST(Fake, result);

		if (pfs_can_become_normal())
		{
			if (type == PermFakeNode && !is_pfs_candidate)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}
}
