import Analysis, Arguments, Runner, Metrics

def _setup():
	import algorithm
	return algorithm._setup_algorithm_paths("psrc_adaptive")

(name, results_path, result_file, result_file_path, graphs_path) = _setup()