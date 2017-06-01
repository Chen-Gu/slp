from __future__ import division

from data.analysis import AnalyzerCommon

import math

import Parameters as p

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)


def sigmoid_funtion(k,value,x0):
    return 1.0 / (1.0 + math.exp(k * (-value - x0)))

def utility_dr(k, value, x0, cutoff, r_dr, cutoff_dr):
    if value <= cutoff:
        return 0.0
    else:
        return sigmoid_funtion(k,value,x0)

def utility_star(k, value, x0, cutoff, r_dr, cutoff_dr):
    if r_dr <= cutoff_dr or value >= cutoff:
        return 0.0
    else:
        return sigmoid_funtion(k,-value,x0)

def utility_of(name):
    if name == "ReceiveRatio":
        return utility_dr
    else:
        return utility_star


def utility(x, parameters):
    r_dr, cutoff_dr = 0, 0
    for (name, k, x0, cutoff, weight) in parameters:
        if name == "ReceiveRatio":
            r_dr, cutoff_dr = x.average_of[name], cutoff

    
    #for (name, k, x0, cutoff, weight) in parameters:
    #    print "utility of {}: {}".format(name, utility_of(name)(k,x.average_of[name], x0, cutoff, r_dr, cutoff_dr))

    return sum(
        weight * utility_of(name)(k,x.average_of[name], x0, cutoff, r_dr, cutoff_dr)
        for (name, k, x0, cutoff, weight)
        in parameters
    )

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return [
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
        ]

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['beacon']             = lambda x: AnalyzerCommon._format_results(x, 'BeaconSent')

        d['paths reached end']  = lambda x: AnalyzerCommon._format_results(x, 'PathsReachedEnd')
        d['source dropped']     = lambda x: AnalyzerCommon._format_results(x, 'SourceDropped')
        d['path dropped']       = lambda x: AnalyzerCommon._format_results(x, 'PathDropped', allow_missing=True)
        d['path dropped length']= lambda x: AnalyzerCommon._format_results(x, 'PathDroppedLength', allow_missing=True)

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')

        d['utility habitat']     = lambda x: str(utility(x, [("Captured",               p.habitat_cr["k"], p.habitat_cr["x0"], p.habitat_cr["cutoff"], p.habitat_cr["weight"]),   # k value, x0 value, capture ratio(ranges from [0, 1])
                                                            ("ReceiveRatio",           p.habitat_dr["k"], p.habitat_dr["x0"], p.habitat_dr["cutoff"], p.habitat_dr["weight"]),   # k value, x0 value, receive ratio(ranges from [0, 1])
                                                            ("NormalLatency",          p.habitat_lat["k"], p.habitat_lat["x0"], p.habitat_lat["cutoff"], p.habitat_lat["weight"]),    # k value, x0 value, latency(scale is in seconds)
                                                            ("norm(Sent,TimeTaken)", p.habitat_msg["k"], p.habitat_msg["x0"], p.habitat_msg["cutoff"], p.habitat_msg["weight"])]))  # k value, x0 value, message send numbers

        d['utility military']     = lambda x: str(utility(x, [("Captured",               p.military_cr["k"], p.military_cr["x0"], p.military_cr["cutoff"], p.military_cr["weight"]),   # k value, x0 value, capture ratio(ranges from [0, 1])
                                                            ("ReceiveRatio",          p.military_dr["k"], p.military_dr["x0"], p.military_dr["cutoff"], p.military_dr["weight"]),   # k value, x0 value, receive ratio(ranges from [0, 1])
                                                            ("NormalLatency",          p.military_lat["k"], p.military_lat["x0"], p.military_lat["cutoff"], p.military_lat["weight"]),    # k value, x0 value, latency(scale is in seconds)
                                                            ("norm(Sent,TimeTaken)", p.military_msg["k"], p.military_msg["x0"], p.military_msg["cutoff"], p.military_msg["weight"])]))


        return d
