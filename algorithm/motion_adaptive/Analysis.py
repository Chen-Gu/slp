
from collections import OrderedDict

from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return tuple()

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        d['approach']           = lambda x: x.opts['approach']
        
        d['sent']               = lambda x: AnalyzerCommon._format_results(x, 'Sent')
        d['received']           = lambda x: AnalyzerCommon._format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance')
        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: AnalyzerCommon._format_results(x, 'TimeTaken')
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['choose']             = lambda x: AnalyzerCommon._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: AnalyzerCommon._format_results(x, 'FakeSent')
        d['tfs']                = lambda x: AnalyzerCommon._format_results(x, 'TFS')
        d['pfs']                = lambda x: AnalyzerCommon._format_results(x, 'PFS')
        d['fake to normal']     = lambda x: AnalyzerCommon._format_results(x, 'FakeToNormal')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource')
        d['src change detected'] = lambda x: AnalyzerCommon._format_results(x, 'SourceChangeDetected')
        d['detected src change'] = lambda x: AnalyzerCommon._format_results(x, 'NodesDetectedSrcChange')

        d['wall time']          = lambda x: AnalyzerCommon._format_results(x, 'WallTime')
        d['event count']        = lambda x: AnalyzerCommon._format_results(x, 'EventCount')
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        return d
