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
	
	App.Boot -> MainC;
	App.Leds -> LedsC;

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
	App.Packet -> ActiveMessageC;
	App.AMPacket -> ActiveMessageC;

	// Timers
	components new TimerMilliC() as AwaySenderTimer;
	components new TimerMilliC() as DisableSenderTimer;

	App.AwaySenderTimer -> AwaySenderTimer;
	App.DisableSenderTimer -> DisableSenderTimer;

	// Networking
	components
		new AMSenderC(NORMAL_FLOOD_CHANNEL) as NormalFloodSender,
		new AMReceiverC(NORMAL_FLOOD_CHANNEL) as NormalFloodReceiver;

	App.NormalFloodSend -> NormalFloodSender;
	App.NormalFloodReceive -> NormalFloodReceiver;

	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	components
		new AMSenderC(DISABLE_CHANNEL) as DisableSender,
		new AMReceiverC(DISABLE_CHANNEL) as DisableReceiver;

	App.DisableSend -> DisableSender;
	App.DisableReceive -> DisableReceiver;

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components CollectionC;
	App.RoutingControl -> CollectionC;
	App.RootControl -> CollectionC;
	//App.CollectionPacket -> CollectionC;
	//App.CtpInfo -> CollectionC;
	//App.CtpCongestion -> CollectionC;

	components new CollectionSenderC(NORMAL_CHANNEL);

	// Networking
	App.NormalSend -> CollectionSenderC;
	App.NormalReceive -> CollectionC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> CollectionC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> CollectionC.Intercept[NORMAL_CHANNEL];

	components CTPMetricsP;
	CTPMetricsP.MetricLogging -> MetricLogging;
	CTPMetricsP.MetricHelpers -> MetricHelpers;
	CTPMetricsP.CtpInfo -> CollectionC;
	CollectionC.CollectionDebug -> CTPMetricsP;
}
