#include "Constants.h"

#include <Timer.h>

configuration SourceBroadcasterAppC
{
}

implementation
{
	// The application
	components SourceBroadcasterC as App;

	// Low levels events such as boot and LED control
	components DelayedBootEventMainP as MainC;
	components LedsWhenGuiC as LedsC;
	components RandomC;
	components CrcC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;
	App.Random -> RandomC;
	App.Crc -> CrcC;

	components MetricLoggingP as MetricLogging;
	App.MetricLogging -> MetricLogging;
	
	components MetricHelpersP as MetricHelpers;
	App.MetricHelpers -> MetricHelpers;

	components new NodeTypeC(6);
	App.NodeType -> NodeTypeC;
	NodeTypeC.MetricLogging -> MetricLogging;

	components new MessageTypeC(6);
	App.MessageType -> MessageTypeC;
	MessageTypeC.MetricLogging -> MetricLogging;

	MetricLogging.MessageType -> MessageTypeC;

	// Radio Control
	components ActiveMessageC;
	App.RadioControl -> ActiveMessageC;
	App.PacketTimeStamp -> ActiveMessageC;

	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;

	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;
	components new TimerMilliC() as AwaySenderTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;
	App.AwaySenderTimer -> AwaySenderTimer;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
	
	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;

	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	components
		new AMSenderC(CHOOSE_CHANNEL) as ChooseSender,
		new AMReceiverC(CHOOSE_CHANNEL) as ChooseReceiver;

	App.ChooseSend -> ChooseSender;
	App.ChooseReceive -> ChooseReceiver;

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;

	components
		new AMSenderC(NOTIFY_CHANNEL) as NotifySender,
		new AMReceiverC(NOTIFY_CHANNEL) as NotifyReceiver;

	App.NotifySend -> NotifySender;
	App.NotifyReceive -> NotifyReceiver;

	components FakeMessageGeneratorP;
	App.FakeMessageGenerator -> FakeMessageGeneratorP;
	FakeMessageGeneratorP.Packet -> ActiveMessageC;
	FakeMessageGeneratorP.MetricLogging -> MetricLogging;
	FakeMessageGeneratorP.MetricHelpers -> MetricHelpers;

	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;
}
