'''
IrisAO helper functions go here


Functions needs:
- Command individual segment with PTT
- Global segment commands
- Mirror release
- Apply IrisAO flat
'''
import csv
import subprocess
import numpy as np

def apply_ptt_command(pttlist, outpath, mserial='PWA37-05-04-0404', dserial='09150004',
                      script_path='/home/lab/IrisAO/SourceCodes', hardware_disable=False,):
    # write ptt command to file
    write_ptt_command(pttlist, outpath)

    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sh', 'SendPTT', mserial, dserial, int(hardware_disable), outpath],
                     cwd=script_path)

def release_mirror(script_path='/home/lab/IrisAO/SourceCodes'):
    # run Alex's C code (needs to have root privileges...)
    subprocess.call(['sh', 'Release'], cwd=script_path)

def build_global_zmode():
    '''
    Magic happens here. I don't even know if I want to do this, or if I
    just want to use IrisAO's prebuilt global modes.
    '''
    pass

def build_ptt_command(nsegments=37, piston=0., tip=0., tilt=0.):
    '''
    Build a nsegment-length list of lists containing the [piston, tip, tilt]
    commands to send to each segment of the IrisAO DM.

    Piston = microns
    Tip, tilt = millirad

    If PTT are floats, will be applied globally.
    If they are a list of length nsegments, then
    they'll be applied to the segments individually.

    If no arguments are given, will build the PTT list for a 37-segment
    DM with not PTT applied.

    Parameters:


    Returns:


    '''
    pttlist = [[0.,0.,0.] for i in range(nsegments)]

    if isinstance(piston, float):
        for ptt in pttlist:
            ptt[0] = piston
    elif isinstance(piston, (list, tuple, np.ndarray)) and len(piston) == nsegments:
        for ptt, p in zip(pttlist, piston):
            ptt[0] = p
    else:
        raise TypeError('piston is neither a float nor an array-like with length {}!'.format(nsegments))

    if isinstance(tip, float):
        for ptt in pttlist:
            ptt[1] = tip
    elif isinstance(tip, (list, tuple, np.ndarray)) and len(tip) == nsegments:
        for ptt, t in zip(pttlist, tip):
            ptt[1] = t
    else:
        raise TypeError('tip is neither a float nor an array-like with length {}!'.format(nsegments))

    if isinstance(tilt, float):
        for ptt in pttlist:
            ptt[2] = tilt
    elif isinstance(tilt, (list, tuple, np.ndarray)) and len(tilt) == nsegments:
        for ptt, t in zip(pttlist, tilt):
            ptt[2] = t
    else:
        raise TypeError('tilt is neither a float nor an array-like with length {}!'.format(nsegments))

    return pttlist

def write_ptt_command(pttlist, outname):
    with open(outname, 'w+') as f:
        writer = csv.writer(f, delimiter=' ', lineterminator='\n')
        writer.writerows(pttlist)

def read_ptt_command(filename):
    with open(filename, 'r') as f:
        reader = csv.reader(f, delimiter=' ', quoting=csv.QUOTE_NONNUMERIC)
        pttlist = [line for line in reader]
    return pttlist
