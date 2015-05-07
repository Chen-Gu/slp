#include "FakeMessage.h"

#define DEBUG_PREFIX "%s: "
#define DEBUG_ARGS sim_time_string()

#define mydbg(type, message, ...) dbg(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)
#define myerr(type, message, ...) dbgerror(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)

module FakeMessageGeneratorImplP
{
	provides
	{
		interface FakeMessageGenerator;
	}
	uses
	{
		interface Timer<TMilli> as SendFakeTimer;
		interface Timer<TMilli> as DurationTimer;

		interface Packet;
		interface AMSend as FakeSend;
	}
}
implementation
{
	AwayChooseMessage original_message;

	// Network variables

	bool busy = FALSE;
	message_t packet;

	// Implementation

	command void FakeMessageGenerator.start(const AwayChooseMessage* original)
	{
		original_message = *original;

		// The first fake message is to be sent half way through the period.
		// After this message is sent, all other messages are sent with an interval
		// of the period given. The aim here is to reduce the traffic at the start and
		// end of the TFS duration.
		call SendFakeTimer.startOneShot((signal FakeMessageGenerator.calculatePeriod()) / 2);
	}

	command void FakeMessageGenerator.startLimited(const AwayChooseMessage* original, uint32_t duration_ms)
	{
		call FakeMessageGenerator.start(original);

		call DurationTimer.startOneShot(duration_ms);

		mydbg("FakeMessageGeneratorImplP", "SendFakeTimer started limited with a duration of %u ms.\n", duration_ms);
	}

	command void FakeMessageGenerator.stop()
	{
		call DurationTimer.stop();
		call SendFakeTimer.stop();
	}

	default event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		return 0;
	}
	
	default event void FakeMessageGenerator.sent(error_t error, const FakeMessage* message)
	{
	}

	bool send_fake_message()
	{
		error_t status;
		FakeMessage message;

		signal FakeMessageGenerator.generateFakeMessage(&message);

		if (!busy)
		{
			void* const void_tosend = call Packet.getPayload(&packet, sizeof(FakeMessage));
			FakeMessage* const tosend = (FakeMessage*)void_tosend;
			if (tosend == NULL)
			{
				myerr("FakeMessageGeneratorImplP", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			*tosend = message;

			status = call FakeSend.send(AM_BROADCAST_ADDR, &packet, sizeof(FakeMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			signal FakeMessageGenerator.sent(status, &message);

			return status == SUCCESS;
		}
		else
		{
			signal FakeMessageGenerator.sent(EBUSY, &message);

			myerr("SourceBroadcasterC", "BroadcastAway busy, not forwarding Away message.\n");
			return FALSE;
		}
	}

	event void SendFakeTimer.fired()
	{
		uint32_t period;

		mydbg("FakeMessageGeneratorImplP", "SendFakeTimer fired.\n");

		send_fake_message();

		period = signal FakeMessageGenerator.calculatePeriod();

		if (period > 0)
		{
			call SendFakeTimer.startOneShot(period);
		}
	}

	event void FakeSend.sendDone(message_t* msg, error_t error)
	{
		mydbg("FakeMessageGeneratorImplP", "FakeSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	event void DurationTimer.fired()
	{
		mydbg("FakeMessageGeneratorImplP", "DurationTimer fired.\n");

		call FakeMessageGenerator.expireDuration();
	}

	command void FakeMessageGenerator.expireDuration()
	{
		call FakeMessageGenerator.stop();
		signal FakeMessageGenerator.durationExpired(&original_message);
	}
}