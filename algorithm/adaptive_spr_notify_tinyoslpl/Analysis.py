
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
            (('Sent', 'TimeTaken'), 'source_rate'),
            ((('Sent', 'TimeTaken'), 'num_nodes'), 'source_rate'),

            ('FakeSent', 'TimeTaken'),
            (('FakeSent', 'TimeTaken'), 'num_nodes'),
            (('FakeSent', 'TimeTaken'), 'source_rate'),
            ((('FakeSent', 'TimeTaken'), 'num_nodes'), 'source_rate'),

            ('NormalSent', 'TimeTaken'),

            ('average_duty_cycle', '1'),
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)
        
        d['normal']             = lambda x: self._format_results(x, 'NormalSent')
        d['away']               = lambda x: self._format_results(x, 'AwaySent')
        d['choose']             = lambda x: self._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: self._format_results(x, 'FakeSent')
        d['beacon']             = lambda x: self._format_results(x, 'BeaconSent')
        d['notify']             = lambda x: self._format_results(x, 'NotifySent')
        d['tfs']                = lambda x: self._format_results(x, 'TFS')
        d['pfs']                = lambda x: self._format_results(x, 'PFS')
        d['tailfs']             = lambda x: self._format_results(x, 'TailFS')
        d['fake to normal']     = lambda x: self._format_results(x, 'FakeToNormal')
        d['fake to fake']       = lambda x: self._format_results(x, 'FakeToFake')
        
        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
        d['norm(norm(sent,time taken),source rate)'] = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),source_rate)')
        d['norm(norm(norm(sent,time taken),network size),source rate)']   = lambda x: self._format_results(x, 'norm(norm(norm(Sent,TimeTaken),num_nodes),source_rate)')

        d['norm(fake,time taken)']   = lambda x: self._format_results(x, 'norm(FakeSent,TimeTaken)')
        d['norm(norm(fake,time taken),network size)']   = lambda x: self._format_results(x, 'norm(norm(FakeSent,TimeTaken),num_nodes)')
        d['norm(norm(fake,time taken),source rate)'] = lambda x: self._format_results(x, 'norm(norm(FakeSent,TimeTaken),source_rate)')
        d['norm(norm(norm(fake,time taken),network size),source rate)']   = lambda x: self._format_results(x, 'norm(norm(norm(FakeSent,TimeTaken),num_nodes),source_rate)')

        d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')

        d['average duty cycle']   = lambda x: self._format_results(x, 'norm(average_duty_cycle,1)')

        return d
