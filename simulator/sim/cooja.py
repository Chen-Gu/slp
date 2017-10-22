from __future__ import print_function, division

generate_per_node_id_binary = False

def parsers():
    raw_single_common = ["verbose", "seed", "configuration", "network size", "distance",
                         "fault model", "node id order", "safety period", "start time",
                         "low power listening", "cooja", "cc2420"]

    return [
        ("SINGLE", None, raw_single_common + ["attacker model"]),
        ("RAW", None, raw_single_common),
        ("GUI", "SINGLE", ["gui scale"]),
        ("PARALLEL", "SINGLE", ["job size"]),
        ("CLUSTER", "PARALLEL", ["job id"]),
    ]

def supports_parallel():
    return True

def build(module, a):
    import data.cycle_accurate
    from data.run.driver.cycle_accurate_builder import Runner as Builder

    from data import submodule_loader

    target = module.replace(".", "/") + ".txt"

    cooja = submodule_loader.load(data.cycle_accurate, "cooja")

    builder = Builder(cooja, platform=a.args.platform.platform())
    builder.total_job_size = 1
    
    #(a, module, module_path, target_directory)
    builder.add_job((module, a), target)

def print_version():
    import simulator.VersionDetection as VersionDetection

    print("@version:tinyos={}".format(VersionDetection.tinyos_version()))
    print("@version:contiki={}".format(VersionDetection.contiki_version()))

    print("@version:java={}".format(VersionDetection.java_version()))

def cooja_command(module, a, configuration):
    import os

    try:
        cooja_path = os.path.join(os.environ["CONTIKI_DIR"], "tools", "cooja", "dist", "cooja.jar")
    except KeyError:
        raise RuntimeError("Unable to find the environment variable AVRORA_JAR_PATH so cannot run avrora.")

    target_directory = module.replace(".", "/")

    csc_file = os.path.join(target_directory, "build", "sim.csc")

    if not os.path.exists(csc_file):
        raise RuntimeError("The csc file does not exist at {}".format(csc_file))

    command = "java -jar '{}' -nogui='{}' -contiki='{}'".format(cooja_path, csc_file, os.environ["CONTIKI_DIR"])

    return command


def cooja_iter(iterable):
    from datetime import datetime

    for line in iterable:
        line = line.rstrip()

        time_us, rest = line.split("|", 1)

        time_s = float(time_us) / 1000000.0

        node_time = datetime.fromtimestamp(time_s)

        stime_str = node_time.strftime("%Y/%m/%d %H:%M:%S.%f")

        yield stime_str + "|" + rest

def print_arguments(module, a):
    for (k, v) in sorted(vars(a.args).items()):
        if k not in a.arguments_to_hide:
            print("{}={}".format(k, v))

def run_simulation(module, a, count=1, print_warnings=False):
    global base64, pickle, re

    import base64
    import pickle
    import re
    import shlex
    import sys

    try:
        import subprocess32 as subprocess
    except ImportError:
        import subprocess

    from simulator import Configuration

    configuration = Configuration.create(a.args.configuration, a.args)

    command = cooja_command(module, a, configuration)

    print("@command:{}".format(command))
    sys.stdout.flush()

    command = shlex.split(command)    

    if a.args.mode == "RAW":
        if count != 1:
            raise RuntimeError("Cannot run cooja multiple times in RAW mode")

        proc = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

        proc_iter = iter(proc.stderr.readline, '')

        for line in avrora_iter(proc_iter):
            print(line)

        proc.stderr.close()

        return_code = proc.wait()

        #if return_code:
        #    raise subprocess.CalledProcessError(return_code, command)

    else:
        import copy

        if a.args.mode == "SINGLE":
            from simulator.Simulation import OfflineSimulation
        elif a.args.mode == "GUI":
            from simulator.TosVis import GuiOfflineSimulation as OfflineSimulation
        else:
            raise RuntimeError("Unknown mode {}".format(a.args.mode))

        for n in range(count):
            proc = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

            proc_iter = iter(proc.stderr.readline, '')

            with OfflineSimulation(module, configuration, a.args, event_log=cooja_iter(proc_iter)) as sim:
                # Create a copy of the provided attacker model
                attacker = copy.deepcopy(a.args.attacker_model)

                if len(configuration.sink_ids) != 1:
                    raise RuntimeError("Attacker does not know where to start!")

                attacker_start = next(iter(configuration.sink_ids))

                # Setup each attacker model
                attacker.setup(sim, attacker_start, ident=0)

                sim.add_attacker(attacker)

                try:
                    sim.run()
                except Exception as ex:
                    import traceback
                    
                    all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                    print("Killing run due to {}".format(ex), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    print("For parameters:", file=sys.stderr)
                    print(all_args, file=sys.stderr)

                    # Make sure to kill the avrora java process
                    proc.kill()

                    return 51

                proc.stderr.close()

                return_code = proc.wait()

                #if return_code:
                #    raise subprocess.CalledProcessError(return_code, command)

                try:
                    sim.metrics.print_results()

                    if print_warnings:
                        sim.metrics.print_warnings()

                except Exception as ex:
                    import traceback

                    all_args = "\n".join("{}={}".format(k, v) for (k, v) in vars(a.args).items() if k not in a.arguments_to_hide)

                    print("Failed to print metrics due to: {}".format(ex), file=sys.stderr)
                    print(traceback.format_exc(), file=sys.stderr)
                    print("For parameters:", file=sys.stderr)
                    print(all_args, file=sys.stderr)

                    # Make sure to kill the avrora java process
                    proc.kill()
                    
                    return 52