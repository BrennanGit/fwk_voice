# Copyright 2021 XMOS LIMITED.
# This Software is subject to the terms of the XMOS Public Licence: Version 1.
import argparse
import numpy as np
import os.path

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", nargs='?', default='2 2 2 10 5', help="Build configuration in '<threads> <num_y_channels> <num_x_channels> <num_main_filter_phases> <num_shadow_filter_phases>' format. Default '2 2 2 10 5'")
    parser.add_argument("--out-dir", nargs='?', default='.', help="output directory to generate files in. Default .")
    args = parser.parse_args()
    return args

#Schedule num_tasks tasks, each having num_channels channels over num_threads threads
def gen_schedule(num_threads, num_tasks, num_channels):
    #Scheduling logic - T0C0, T1C0, T2C0, T0C1, T1C1, T2C2 and so on
    if num_channels:
        remaining_jobs = num_tasks * num_channels
    else:
        remaining_jobs = num_tasks;
    pas = 0
    sch = np.zeros((num_threads,1), dtype=np.int32)
    thread = 0

    task_index = 0
    ch_index = 0
    while(remaining_jobs):
        #bit 16:9 task_index, bit8:1 ch_index, bit0, is_active 
        sch[thread, pas] = (1 | (((ch_index & 0xff) << 1) | ((task_index & 0xff) << 9)))
        task_index = task_index + 1
        if(task_index == num_tasks):
            task_index = 0
            if num_channels:
                ch_index = (ch_index + 1) % num_channels

        thread += 1
        remaining_jobs -= 1
        if(thread == num_threads and remaining_jobs): #add another pass
            thread = 0
            pas += 1
            append_sch = np.zeros((num_threads, 1), dtype=np.int32)
            sch = np.hstack((sch, append_sch))
    pas += 1
    return sch

def print_schedule(sch, num_tasks, num_channels, fp_sch_h, fp_c, schedule_t_str):
    num_threads = sch.shape[0]
    num_passes = sch.shape[-1]
    threads_str = "AEC_THREAD_COUNT"
    if num_channels:
        passes_str = f"AEC_{num_tasks}_TASKS_AND_CHANNELS_PASSES"
        struct_typedef = "par_tasks_and_channels_t"
        schedule_t_str = schedule_t_str + f"{struct_typedef} par_{num_tasks}_tasks_and_channels[{threads_str}][{passes_str}];\n"
    else:
        passes_str = f"AEC_{num_tasks}_TASKS_PASSES"
        struct_typedef = "par_tasks_t"
        schedule_t_str = schedule_t_str + f"{struct_typedef} par_{num_tasks}_tasks[{threads_str}][{passes_str}];\n"

    fp_sch_h.write(f'#define {passes_str}   ({num_passes})' + '\n')
    fp_c.write("{\n")
    for t in range(num_threads):
        thread_str = "  {" 
        for p in range(num_passes):
            task = (sch[t][p] >> 9);
            ch = (sch[t][p] >> 1) & 0xff;
            active = sch[t][p] & 1;
            if num_channels:
                ph_str = "{" + f"{task}, {ch}, {active}" "}"
            else:
                ph_str = "{" + f"{task}, {active}" "}"
            thread_str = thread_str + ph_str + ','
        thread_str += "},"
        fp_c.write(thread_str+'\n')
    fp_c.write("},\n")
    return schedule_t_str


def create_schedule():
    args = parse_arguments()
    print('config = ',args.config)
    print('out-dir = ',args.out_dir)
    conf = args.config.split(' ')
    threads = conf[0]
    max_y_channels = conf[1]
    max_x_channels = conf[2]
    main_filter_phases = conf[3]
    shadow_filter_phases = conf[4]
    print(f"AEC schedule generation configured for {threads} threads, max {max_y_channels} y channels, max {max_x_channels} x channels, {main_filter_phases} main_filter_phases, {shadow_filter_phases} shadow_filter_phases")
    autogen_message = '/* Do not edit, autogenerated */ '
    sch_h_file_name = os.path.join(args.out_dir, "aec_schedule.h")
    cfg_h_file_name = os.path.join(args.out_dir, "aec_config.h")
    c_file_name = os.path.join(args.out_dir, "aec_schedule.c")

    fp_sch_h = open(sch_h_file_name, 'w')
    fp_cfg_h = open(cfg_h_file_name, 'w')
    fp_c = open(c_file_name, 'w')
    fp_sch_h.write( '#ifndef aec_schedule_h_\n')
    fp_sch_h.write( '#define aec_schedule_h_\n')

    fp_cfg_h.write( '#ifndef aec_config_h_\n')
    fp_cfg_h.write( '#define aec_config_h_\n')
    #schedule multiple tasks across multiple channels on different cores 
    par_tasks_and_channels_t = "typedef struct {\n" + "    int task;\n" + "    int channel;\n" + "    int is_active;\n" + "}par_tasks_and_channels_t;\n\n"  
    par_tasks_t = "typedef struct {\n" + "    int task;\n" + "    int is_active;\n" + "}par_tasks_t;\n\n"  
    schedule_t_str = par_tasks_and_channels_t + par_tasks_t + "typedef struct {\n"

    num_channels = max(int(max_y_channels), int(max_x_channels))
    num_threads = int(threads)
    num_main_filter_phases = int(main_filter_phases)
    num_shadow_filter_phases = int(shadow_filter_phases)
    fp_sch_h.write(autogen_message + '\n')    
    fp_cfg_h.write(autogen_message + '\n')    
    threads_str = "AEC_THREAD_COUNT"
    threads_define = f"#define {threads_str}   ({num_threads})"
    fp_sch_h.write(threads_define + '\n')
    fp_cfg_h.write(f"#define AEC_MAX_Y_CHANNELS   ({max_y_channels})\n")
    fp_cfg_h.write(f"#define AEC_MAX_X_CHANNELS   ({max_x_channels})\n")
    fp_cfg_h.write(f"#define AEC_MAIN_FILTER_PHASES    ({main_filter_phases})\n")
    fp_cfg_h.write(f"#define AEC_SHADOW_FILTER_PHASES    ({shadow_filter_phases})\n")

    fp_c.write( autogen_message + '\n')
    fp_c.write( f'#include "{sch_h_file_name}"\n')
    fp_c.write( 'schedule_t sch = {\n')
    #Schedule 3 tasks, num_channels channels over num_threads threads
    sch = gen_schedule(num_threads, 3, num_channels)
    schedule_t_str = print_schedule(sch, 3, num_channels, fp_sch_h, fp_c, schedule_t_str);

    #Schedule 2 tasks, num_channels channels over num_threads threads
    sch = gen_schedule(num_threads, 2, num_channels)
    schedule_t_str = print_schedule(sch, 2, num_channels, fp_sch_h, fp_c, schedule_t_str)

    #Schedule 1 tasks, num_channels channels over num_threads threads
    sch = gen_schedule(num_threads, 1, num_channels)
    schedule_t_str = print_schedule(sch, 1, num_channels, fp_sch_h, fp_c,  schedule_t_str)

    #Schedule multiple tasks on different cores 
    #Schedule 2 tasks
    sch = gen_schedule(num_threads, 2, 0)
    schedule_t_str = print_schedule(sch, 2, 0, fp_sch_h, fp_c,  schedule_t_str)

    #Schedule 3 tasks
    sch = gen_schedule(num_threads, 3, 0)
    schedule_t_str = print_schedule(sch, 3, 0, fp_sch_h, fp_c,  schedule_t_str)

    schedule_t_str += '}schedule_t;\n'
    fp_sch_h.write(schedule_t_str+'\n')
    fp_sch_h.write( '#endif /* aec_schedule_h_ */')
    fp_cfg_h.write( '#endif /* aec_config_h_ */')
    fp_c.write( '};\n')
    fp_sch_h.close()
    fp_cfg_h.close()
    fp_c.close()

if __name__ == "__main__":
    create_schedule()
