
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
	
	def normalised_parameters(self):
		return (
            ('Sent', 'TimeTaken'),
            #(('Sent', 'TimeTaken'), 'num_nodes'),

            ('Captured', 'ReceiveRatio'),
            (('Sent', 'TimeTaken'), 'ReceiveRatio'),
        )

	def results_header(self):
		d = self.common_results_header(algorithm_module.local_parameter_names)

		self.common_results(d)

		#d['normalised captured']	= lambda x: self._format_results(x, 'norm(Captured,ReceiveRatio)')
		
		d['normal']             = lambda x: self._format_results(x, 'NormalSent')
		d['away']               = lambda x: self._format_results(x, 'AwaySent')
		d['beacon']             = lambda x: self._format_results(x, 'BeaconSent')

		#d['paths reached end']  = lambda x: self._format_results(x, 'PathsReachedEnd')
		#d['source dropped']     = lambda x: self._format_results(x, 'SourceDropped')
		#d['path dropped']       = lambda x: self._format_results(x, 'PathDropped', allow_missing=True)
		#d['path dropped length']= lambda x: self._format_results(x, 'PathDroppedLength', allow_missing=True)
		
		#d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
		#d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

		d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
		#d['norm(norm(sent,time taken),num_nodes)']   = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
		#d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')

		return d
