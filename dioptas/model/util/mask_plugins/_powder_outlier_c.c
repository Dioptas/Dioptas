/*
 * SPDX-License-Identifier: MIT
 *
 * Fast per-bin outlier detection for powder diffraction spot masking.
 *
 * Provides both mean/std and median/MAD methods.
 * Expects pixels pre-sorted by 2-theta into equal-count bins.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>


/* ---- Quickselect (introselect variant) ---- */

static inline void swap_d(double *a, double *b) {
    double t = *a; *a = *b; *b = t;
}

static void insertion_sort_d(double *arr, Py_ssize_t n) {
    for (Py_ssize_t i = 1; i < n; i++) {
        double key = arr[i];
        Py_ssize_t j = i - 1;
        while (j >= 0 && arr[j] > key) {
            arr[j + 1] = arr[j];
            j--;
        }
        arr[j + 1] = key;
    }
}

static double quickselect_k(double *arr, Py_ssize_t n, Py_ssize_t k) {
    Py_ssize_t lo = 0, hi = n - 1;

    while (hi - lo > 16) {
        /* Median-of-three pivot */
        Py_ssize_t mid = lo + (hi - lo) / 2;
        if (arr[lo] > arr[mid]) swap_d(&arr[lo], &arr[mid]);
        if (arr[lo] > arr[hi])  swap_d(&arr[lo], &arr[hi]);
        if (arr[mid] > arr[hi]) swap_d(&arr[mid], &arr[hi]);
        swap_d(&arr[mid], &arr[hi - 1]);
        double pivot = arr[hi - 1];

        Py_ssize_t i = lo, j = hi - 1;
        for (;;) {
            while (arr[++i] < pivot);
            while (arr[--j] > pivot);
            if (i >= j) break;
            swap_d(&arr[i], &arr[j]);
        }
        swap_d(&arr[i], &arr[hi - 1]);

        if (i == k) return arr[k];
        else if (i < k) lo = i + 1;
        else hi = i - 1;
    }

    insertion_sort_d(arr + lo, hi - lo + 1);
    return arr[k];
}


/*
 * compute_outlier_mask(sorted_img, num_bins, pixels_per_bin, esdmul, use_median)
 *
 * sorted_img:     contiguous 1D float64, length >= num_bins * pixels_per_bin
 * num_bins:       number of equal-count bins
 * pixels_per_bin: pixels per bin
 * esdmul:        threshold multiplier
 * use_median:    if true, use median/MAD; if false, use mean/std
 *
 * Returns: 1D uint8 mask array (1 = outlier)
 */
static PyObject *
compute_outlier_mask(PyObject *self, PyObject *args)
{
    PyArrayObject *sorted_img_arr;
    int num_bins, pixels_per_bin, use_median;
    double esdmul;

    if (!PyArg_ParseTuple(args, "O!iidp",
                          &PyArray_Type, &sorted_img_arr,
                          &num_bins, &pixels_per_bin, &esdmul, &use_median))
        return NULL;

    if (PyArray_NDIM(sorted_img_arr) != 1 ||
        PyArray_TYPE(sorted_img_arr) != NPY_DOUBLE ||
        !PyArray_IS_C_CONTIGUOUS(sorted_img_arr)) {
        PyErr_SetString(PyExc_TypeError,
                        "sorted_img must be a contiguous 1D float64 array");
        return NULL;
    }

    Py_ssize_t ppb = (Py_ssize_t)pixels_per_bin;
    Py_ssize_t total = (Py_ssize_t)num_bins * ppb;
    if (PyArray_SIZE(sorted_img_arr) < total) {
        PyErr_SetString(PyExc_ValueError,
                        "sorted_img too small for num_bins * pixels_per_bin");
        return NULL;
    }

    double *sorted_img = (double *)PyArray_DATA(sorted_img_arr);

    npy_intp dims[1] = {total};
    PyArrayObject *mask_arr =
        (PyArrayObject *)PyArray_ZEROS(1, dims, NPY_UINT8, 0);
    if (mask_arr == NULL) return NULL;
    unsigned char *mask = (unsigned char *)PyArray_DATA(mask_arr);

    double *work = (double *)malloc(ppb * sizeof(double));
    if (work == NULL) { Py_DECREF(mask_arr); return PyErr_NoMemory(); }

    const double mad_scale = 1.4826;
    Py_ssize_t mid = ppb / 2;

    for (int b = 0; b < num_bins; b++) {
        double *bin_data = sorted_img + (Py_ssize_t)b * ppb;
        unsigned char *bin_mask = mask + (Py_ssize_t)b * ppb;
        double center, spread, threshold;

        if (ppb < 3) continue;

        if (use_median) {
            /* Median via quickselect */
            memcpy(work, bin_data, ppb * sizeof(double));
            center = quickselect_k(work, ppb, mid);

            /* MAD */
            for (Py_ssize_t i = 0; i < ppb; i++)
                work[i] = fabs(bin_data[i] - center);
            spread = quickselect_k(work, ppb, mid) * mad_scale;

            /* Fallback to std when MAD is 0 (near-uniform bin) */
            if (spread <= 0.0) {
                double sum = 0.0, sum2 = 0.0;
                for (Py_ssize_t i = 0; i < ppb; i++) {
                    sum += bin_data[i];
                    sum2 += bin_data[i] * bin_data[i];
                }
                double mean = sum / ppb;
                double var = sum2 / ppb - mean * mean;
                spread = (var > 0.0) ? sqrt(var) : 0.0;
            }
        } else {
            /* Mean + Std */
            double sum = 0.0, sum2 = 0.0;
            for (Py_ssize_t i = 0; i < ppb; i++) {
                sum += bin_data[i];
                sum2 += bin_data[i] * bin_data[i];
            }
            center = sum / ppb;
            double var = sum2 / ppb - center * center;
            spread = (var > 0.0) ? sqrt(var) : 0.0;
        }

        if (spread <= 0.0) continue;

        threshold = center + esdmul * spread;

        for (Py_ssize_t i = 0; i < ppb; i++) {
            if (bin_data[i] > threshold)
                bin_mask[i] = 1;
        }
    }

    free(work);
    return (PyObject *)mask_arr;
}


static PyMethodDef methods[] = {
    {"compute_outlier_mask", compute_outlier_mask, METH_VARARGS,
     "Compute outlier mask from pre-sorted image data.\n\n"
     "Args:\n"
     "    sorted_img: 1D float64 array sorted by 2-theta\n"
     "    num_bins: number of equal-count bins\n"
     "    pixels_per_bin: pixels in each bin\n"
     "    esdmul: threshold in sigma/MAD units\n"
     "    use_median: True for median/MAD, False for mean/std\n"},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT,
    "_powder_outlier_c",
    "C-accelerated powder diffraction outlier mask computation.",
    -1,
    methods
};

PyMODINIT_FUNC
PyInit__powder_outlier_c(void)
{
    import_array();
    return PyModule_Create(&module);
}
