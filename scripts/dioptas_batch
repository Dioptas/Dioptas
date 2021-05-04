#!/usr/bin/env python

import argparse
import datetime
import logging
import os
from glob import glob
import numpy as np
from time import time
from multiprocessing import Queue, Pool
import subprocess
import h5py
import re
import psutil
import pyFAI
import sharedmem

data_to_process = Queue()
proc_data = None
mask_shape = None
config = {}
log = logging.getLogger(__name__)


def integrate(args):
    """
    Worker, which perform integration of images from shared queue.

    Result of integration is stored in sharedmem object.

    :param args: List of arguments [index of worker, number of cores to use]
    """
    try:
        i_worker, n_cores = args
        subprocess.check_output(f"taskset -p -c {n_cores * i_worker}-{n_cores * (i_worker + 1) - 1} {os.getpid()}",
                                shell=True)

        # Dioptas is included here after changed the affinity because then it works faster
        from dioptas.model import MaskModel
        from dioptas.model.loader.LambdaLoader import LambdaImage
        from pyFAI.detectors import Detector, ALL_DETECTORS, NexusDetector
        from pyFAI.geometryRefinement import GeometryRefinement

        mask_model = MaskModel()
        mask = None
        pattern_geometry = None

        lambda_img = None
        while not data_to_process.empty():

            try:
                file_list, img_pos, img_id = data_to_process.get(timeout=5)
            except Exception as e:
                # Excepting is taking place is empty() return True for enpty queue.
                pass

            if lambda_img is None or lambda_img.file_list != file_list:
                lambda_img = LambdaImage(file_list=file_list)
                if lambda_img is None:
                    return

            image = lambda_img.get_image(int(img_pos))

            if mask is None and config['mask_file'] is not None:
                mask_model.set_dimension(image.shape)
                mask_model.load_mask(config['mask_file'])
                mask = mask_model.get_mask()
                mask_shape[...] = image.shape

            if pattern_geometry is None:
                # default params are necessary, otherwise fails...
                detector = Detector(pixel1=79e-6, pixel2=79e-6)
                pattern_geometry = GeometryRefinement(wavelength=0.3344e-10, detector=detector,
                                                      poni1=0, poni2=0)
                pattern_geometry.load(config['cal_file'])
                pattern_geometry.detector = Detector(pixel1=pattern_geometry.pixel1, pixel2=pattern_geometry.pixel2)

            ts = time()
            proc_data[img_id] = np.array(pattern_geometry.integrate1d(image, config['num_points'],
                                                     method=config['int_method'],
                                                     unit='2th_deg',
                                                     azimuth_range=None,
                                                     mask=mask,
                                                     polarization_factor=0.99,
                                                     correctSolidAngle=True,
                                                     filename=None))
            log.info(f"Integrate img {img_id}: {(time() - ts):0.3f}s ")

    except Exception as e:
        log.error("Processing fail: {e}", exc_info=True)
        return False
    return True


def fill_queue(raw_files):
    """
    Read number of images in each file-set (3 files for 3 lambda modules) and fill shared queue
    with image indices and corresponding data file

    :param raw_files: List of raw files to process
    :return: number of images, map of files, map of images
    """

    # Group files by file-sets. Check, that all 3 lambda files are present.
    file_sets = []
    for file in sorted(raw_files, key=lambda x: x[-10:]):

        # avoid duplications
        if len(file_sets) > 0 and file in file_sets[-1]:
            continue

        # all 3 files already in a list
        if (re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>1\g<2>', file) in raw_files and
                re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>2\g<2>', file) in raw_files and
                re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>3\g<2>', file) in raw_files):

            file_sets.append([re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>1\g<2>', file),
                              re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>2\g<2>', file),
                              re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>3\g<2>', file)])
        # Files are not in list but exists
        else:
            files = glob(re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>*\g<2>', file))
            if len(files) == 3:
                file_sets.append(sorted(files))

    img_id = 0
    file_map = [0]
    pos_map = []
    for file_set in file_sets:
        data_path = 'entry/instrument/detector/data'
        lambda_file = h5py.File(file_set[0], "r")
        series_max = lambda_file[data_path].shape[0]
        for img_pos in range(series_max):
            data_to_process.put((file_set, img_pos, img_id))
            img_id += 1
        file_map.append(img_id)
        pos_map += list(zip([len(file_map) - 1] * series_max, range(series_max)))
        lambda_file.close()

    return file_sets, img_id, file_map, pos_map


def get_batches(files):
    """
    Create list of batches and their files

    Each batch is one acquisition.

    :param files: List of filepath templates. Each filepath template should be supported by glob.
    :return: List of batches, list of files for each batch
    """

    file_list = []
    name_list = []
    batch_files = []
    for template in files:
        file_list += glob(template)
    file_list = sorted(list(set(file_list)))

    for file_name in file_list:
        batch_name = re.sub('(.+_m)\d((_part\d+|).nxs)', '\g<1>', file_name)[:-2]
        if batch_name not in name_list:
            name_list.append(batch_name)
            batch_files.append([])
        batch_files[name_list.index(batch_name)].append(file_name)

    return name_list, batch_files


def save_proc_data(filename, files, file_map, pos_map):
    """
    Save diffraction patterns to h5 file

    :param filename: Name of output file
    :param files: List of processed files
    :param file_map: Map of files
    :param pos_map: Map of images in the file
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with h5py.File(filename, mode="w") as f:
        f.attrs['default'] = 'processed'
        f.attrs['file_time'] = datetime.datetime.now().isoformat()
        f.attrs['pyFAI_version'] = pyFAI.version

        nxentry = f.create_group('processed')
        nxentry.attrs["NX_class"] = 'NXentry'
        nxentry.attrs['default'] = 'result'

        nxdata = nxentry.create_group('result')
        nxdata.attrs["NX_class"] = 'NXdata'
        nxdata.attrs["signal"] = 'data'
        nxdata.attrs["axes"] = ['.', 'binning']

        nxprocess = nxentry.create_group('process')
        nxprocess.attrs["NX_class"] = 'NXprocess'

        nxprocess['cal_file'] = config['cal_file']
        nxprocess['int_method'] = config['int_method']
        nxprocess['int_unit'] = '2th_deg'
        nxprocess['num_points'] = config['num_points']

        if config['mask_file'] is not None:
            nxprocess['mask_file'] = config['mask_file']
            nxprocess['mask_shape'] = mask_shape

        nxdata.create_dataset("data", data=proc_data[:, 1, :])
        tth = nxdata.create_dataset("binning", data=proc_data[0, 0, :])
        tth.attrs["unit"] = 'deg'
        tth.attrs['long_name'] = 'two_theta (degrees)'

        nxprocess.create_dataset("pos_map", data=np.array(pos_map))
        nxprocess.create_dataset("file_map", data=np.array(file_map))
        nxprocess.create_dataset("files", data=np.array(files).astype('S'))


def run():
    """
    Process all given raw data using multiprocessing pool for parallel processing.

    Result of data processing (integration patterns) is stored together with
    metadata in the nexus file.
    """
    global proc_data
    global mask_shape
    n_cores_all = psutil.cpu_count()
    if config['n_proc'] == 0:
        config['n_proc'] = int(n_cores_all * 0.9 / config['n_cores'])

    args = [[i, config['n_cores']] for i in range(config['n_proc'])]
    name_list, batch_files = get_batches(config['data_path'])
    log.info(f"Total number of batches: {len(name_list)}")

    for i_batch, batch_name in enumerate(name_list):

        ts = time()
        log.info(f"Process batch {i_batch}/{len(name_list)}: {batch_name}")

        try:
            file_sets, n_img, file_map, pos_map = fill_queue(batch_files[i_batch])
            log.info(f"List of files: {file_sets}")
        except Exception as e:
            log.error(f"Reading images for batch {batch_name} fails. {e}")
            continue

        if n_img == 0:
            log.error(f"No images in batch: {batch_name}")
            continue

        proc_data = sharedmem.empty((n_img, 2, config['num_points']), dtype='f4')
        mask_shape = sharedmem.empty(2, dtype='i4')
        log.info(f"Found {n_img} images")

        n_current_proc = min(config['n_proc'], max(1, int(n_img/10.)) )
        log.info(f"Process with {n_current_proc} cores")
        int_time = time()
        with Pool(processes=n_current_proc) as pool:
            status = pool.map(integrate, args)
        int_time = time()-int_time

        if all(status):
            local_path = os.path.basename(batch_name)
            if '/raw/' in batch_name:
                local_path = batch_name[batch_name.find('/raw/')+5:]

            try:
                out_file_name = f"{config['out_path']}/{local_path}_v{config['version']:03d}.nxs"
                save_proc_data(out_file_name, batch_files[i_batch], file_map, pos_map)
                log.info(f"Save file: {out_file_name} {n_img}")
            except Exception as e:
                log.error(f"Saving file {out_file_name} fails: {e}")

            log.info(f"Running time: {time() - ts:0.2f}s for {n_img} images")
            log.info(f"Integration time: {int_time:0.2f}s for {n_img} images")
            log.info(f"Time per image: {int_time / n_img * 1000:0.2f}ms ({n_img})")

    global data_to_process
    del data_to_process
    log.info("All done")


def main():
    """
    Create argparser and logging. Run data processing.
    """
    global config
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Process raw images')

    parser.add_argument('--cal_file', type=str, help='Path to poni file', required=True)
    parser.add_argument('--mask_file', type=str, help='Path to mask file')
    parser.add_argument('--int_method', type=str, help='Integration method',
                        default='csr')
    parser.add_argument('--num_points', type=int, help='Number of points in diffractogram',
                        default=1500)
    parser.add_argument('--out_path', type=str, help='Output path', required=True)
    parser.add_argument('--data_path', type=str, nargs='*',
                        help='Path to raw folder of imput data', required=True)

    parser.add_argument('--n_proc', type=int, help='Number of processes. 0 - 0.9 of all cores',
                        default=0)
    parser.add_argument('--n_cores', type=int, help='Number of cores per process',
                        default=1)
    parser.add_argument('--version', type=int, help='Version of the reprocessing config',
                        default=-1)
    parser.add_argument('--log-file', type=str)
    parser.add_argument("--log_level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        help="Set log level for the application")

    config = vars(parser.parse_args())

    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(filename=config["log_file"],
                        level=getattr(logging, config['log_level']),
                        format=fmt)
    run()


if __name__ == "__main__":
    main()
