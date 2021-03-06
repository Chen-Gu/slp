
#warning "*** USING SLP DUTY CYCLE LOW POWER COMMUNICATIONS ***"

#include "../NormalMessage.h"
#include "../FakeMessage.h"

configuration SLPDutyCycleC
{
    provides
    {
        interface LowPowerListening;
        interface Send;
        interface Receive;
        interface SplitControl;
        interface SLPDutyCycle;
        interface State as SendState;
    }
    uses
    {
        interface Send as SubSend;
        interface Receive as SubReceive;
        interface SplitControl as SubControl;

        interface NodeType;
    }
}
implementation
{
    components SLPDutyCycleP;
    LowPowerListening = SLPDutyCycleP;
    Send = SLPDutyCycleP;
    Receive = SLPDutyCycleP;
    SplitControl = SLPDutyCycleP;
    SLPDutyCycle = SLPDutyCycleP;

    SLPDutyCycleP.NodeType = NodeType;
    SLPDutyCycleP.SubSend = SubSend;
    SLPDutyCycleP.SubReceive = SubReceive;
    SLPDutyCycleP.SubControl = SubControl;

    components MainC;
    MainC.SoftwareInit -> SLPDutyCycleP;

    components LedsC;
    SLPDutyCycleP.Leds -> LedsC;

    components RandomC;
    SLPDutyCycleP.Random -> RandomC;

    components MetricLoggingP as MetricLogging;
    SLPDutyCycleP.MetricLogging -> MetricLogging;

    // CC2420 components
    components CC2420RadioC;
    components CC2420CsmaC;
    components CC2420PacketC;
    components CC2420TransmitC;
    components CC2420ReceiveC;

    SLPDutyCycleP.Resend -> CC2420TransmitC;
    SLPDutyCycleP.PacketAcknowledgements -> CC2420RadioC;
    SLPDutyCycleP.CC2420PacketBody -> CC2420PacketC;
    SLPDutyCycleP.PacketTimeStamp -> CC2420PacketC;
    SLPDutyCycleP.RadioBackoff -> CC2420CsmaC;
    SLPDutyCycleP.EnergyIndicator -> CC2420TransmitC.EnergyIndicator;
    //SLPDutyCycleP.ByteIndicator -> CC2420TransmitC.ByteIndicator;
    SLPDutyCycleP.PacketIndicator -> CC2420ReceiveC.PacketIndicator;

    components new TimerMilliC() as SendDoneTimerC;
    SLPDutyCycleP.SendDoneTimer -> SendDoneTimerC;

    components SystemLowPowerListeningC;  
    SLPDutyCycleP.SystemLowPowerListening -> SystemLowPowerListeningC;

    components new StateC() as SendStateC;
    components new StateC() as RadioPowerStateC;
    components new StateC() as SplitControlStateC;
    SLPDutyCycleP.SendState -> SendStateC;
    SLPDutyCycleP.RadioPowerState -> RadioPowerStateC;
    SLPDutyCycleP.SplitControlState -> SplitControlStateC;

    SendState = SendStateC;

    components LocalTimeMilliC;
    SLPDutyCycleP.LocalTime -> LocalTimeMilliC;

    components new MessageTimingAnalysisP() as NormalMessageTimingAnalysis;
    components new FakeMessageTimingAnalysisP() as FakeMessageTimingAnalysis;
    SLPDutyCycleP.NormalMessageTimingAnalysis -> NormalMessageTimingAnalysis;
    SLPDutyCycleP.FakeMessageTimingAnalysis -> FakeMessageTimingAnalysis;
}
