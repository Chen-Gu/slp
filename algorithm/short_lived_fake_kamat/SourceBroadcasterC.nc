#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define FAKE_SEND_DELAY_MS 20

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as BroadcastFakeTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface ObjectDetector;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode";
		case NormalNode:			return "NormalNode";
		case TempFakeNode:			return "TempFakeNode";
		default:					return "<unknown>";
		}
	}

	SequenceNumber normal_sequence_counter;
	SequenceNumber fake_sequence_counter;

	uint32_t extra_to_send = 0;

	// Produces a random float between 0 and 1
	float random_float(void)
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

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			dbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
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

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			dbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Source\n");

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

			dbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Fake);

	void become_Normal(void)
	{
		const char* const old_type = type_to_string();

		type = NormalNode;

		dbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);
	}

	void become_Fake(NodeType fake_type)
	{
		const char* const old_type = type_to_string();

		if (fake_type != TempFakeNode)
		{
			assert("The perm type is not correct");
		}

		type = fake_type;

		dbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
	}

	event void BroadcastFakeTimer.fired()
	{
		FakeMessage message;

		become_Fake(TempFakeNode);

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.source_id = TOS_NODE_ID;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
		else
		{
			dbgerror("stdout", "Failed to send fake message. Retrying...\n");
			call BroadcastFakeTimer.startOneShot(FAKE_SEND_DELAY_MS);
		}

		become_Normal();
	}

	void process_send_fake_message(void)
	{
		if (random_float() < FAKE_PROBABILITY)
		{
			call BroadcastFakeTimer.startOneShot(FAKE_SEND_DELAY_MS);
		}
	}

	void forward_normal(const NormalMessage* const rcvd)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

			process_send_fake_message();
		}
	}


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		forward_normal(rcvd);
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		forward_normal(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode: Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	void forward_fake(const FakeMessage* const rcvd)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}


	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd);
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd);
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)

}