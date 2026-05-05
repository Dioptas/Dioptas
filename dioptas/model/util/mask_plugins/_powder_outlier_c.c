/*
 * SPDX-License-Identifier: MIT
 *
 * Fast per-bin outlier detection for powder diffraction spot masking.
 *
 * Provides both mean/std and median/MAD methods.
 * Supports equal-width binning (variable bin sizes) via bin_indices.
 * Uses OpenMP for parallel bin processing when available.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#ifdef _OPENMP
#include <omp.h>
#endif


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


/* Process a single bin: compute center, spread, flag outliers */
static void process_bin(
    double *bin_vals, int *bin_pixel_indices,
    Py_ssize_t bsize, double esdmul, int use_median,
    double *work, unsigned char *mask)
{
    if (bsize < 3) return;

    double center, spread;
    Py_ssize_t mid = bsize / 2;

    if (use_median) {
        memcpy(work, bin_vals, bsize * sizeof(double));
        center = quickselect_k(work, bsize, mid);

        for (Py_ssize_t i = 0; i < bsize; i++)
            work[i] = fabs(bin_vals[i] - center);
        spread = quickselect_k(work, bsize, mid) * 1.4826;

        if (spread <= 0.0) {
            double sum = 0.0, sum2 = 0.0;
            for (Py_ssize_t i = 0; i < bsize; i++) {
                sum += bin_vals[i];
                sum2 += bin_vals[i] * bin_vals[i];
            }
            double mean = sum / bsize;
            double var = sum2 / bsize - mean * mean;
            spread = (var > 0.0) ? sqrt(var) : 0.0;
        }
    } else {
        double sum = 0.0, sum2 = 0.0;
        for (Py_ssize_t i = 0; i < bsize; i++) {
            sum += bin_vals[i];
            sum2 += bin_vals[i] * bin_vals[i];
        }
        center = sum / bsize;
        double var = sum2 / bsize - center * center;
        spread = (var > 0.0) ? sqrt(var) : 0.0;
    }

    if (spread <= 0.0) return;

    double threshold = center + esdmul * spread;

    for (Py_ssize_t i = 0; i < bsize; i++) {
        if (bin_vals[i] > threshold)
            mask[bin_pixel_indices[i]] = 1;
    }
}


/*
 * compute_outlier_mask_binned(img, bin_indices, num_bins, esdmul, use_median, num_threads)
 *
 * Equal-width binning: each pixel has a pre-computed bin index.
 *
 * img:          contiguous 1D float64 image data
 * bin_indices:  contiguous 1D int32 array, same length as img, bin index per pixel
 * num_bins:     number of bins
 * esdmul:       threshold multiplier
 * use_median:   True for median/MAD, False for mean/std
 * num_threads:  max OpenMP threads (0 = use default/all available)
 *
 * Returns: 1D uint8 mask array (1 = outlier), same length as img.
 */
static PyObject *
compute_outlier_mask_binned(PyObject *self, PyObject *args)
{
    PyArrayObject *img_arr, *bin_idx_arr;
    int num_bins, use_median, num_threads;
    double esdmul;

    if (!PyArg_ParseTuple(args, "O!O!idpi",
                          &PyArray_Type, &img_arr,
                          &PyArray_Type, &bin_idx_arr,
                          &num_bins, &esdmul, &use_median, &num_threads))
        return NULL;

    if (PyArray_NDIM(img_arr) != 1 ||
        PyArray_TYPE(img_arr) != NPY_DOUBLE ||
        !PyArray_IS_C_CONTIGUOUS(img_arr)) {
        PyErr_SetString(PyExc_TypeError, "img must be a contiguous 1D float64 array");
        return NULL;
    }
    if (PyArray_NDIM(bin_idx_arr) != 1 ||
        PyArray_TYPE(bin_idx_arr) != NPY_INT32 ||
        !PyArray_IS_C_CONTIGUOUS(bin_idx_arr)) {
        PyErr_SetString(PyExc_TypeError, "bin_indices must be a contiguous 1D int32 array");
        return NULL;
    }

    Py_ssize_t n = PyArray_SIZE(img_arr);
    if (PyArray_SIZE(bin_idx_arr) != n) {
        PyErr_SetString(PyExc_ValueError, "img and bin_indices must have the same length");
        return NULL;
    }

    double *img = (double *)PyArray_DATA(img_arr);
    int *bins = (int *)PyArray_DATA(bin_idx_arr);

    /* Output mask */
    npy_intp dims[1] = {n};
    PyArrayObject *mask_arr = (PyArrayObject *)PyArray_ZEROS(1, dims, NPY_UINT8, 0);
    if (mask_arr == NULL) return NULL;
    unsigned char *mask = (unsigned char *)PyArray_DATA(mask_arr);

    /* Phase 1: count pixels per bin */
    int *bin_counts = (int *)calloc(num_bins, sizeof(int));
    if (!bin_counts) { Py_DECREF(mask_arr); return PyErr_NoMemory(); }

    for (Py_ssize_t i = 0; i < n; i++) {
        int b = bins[i];
        if (b >= 0 && b < num_bins)
            bin_counts[b]++;
    }

    /* Find max bin size for work buffer allocation */
    int max_bin = 0;
    for (int b = 0; b < num_bins; b++)
        if (bin_counts[b] > max_bin) max_bin = bin_counts[b];

    /* Phase 2: collect pixel indices and values per bin */
    /* Allocate flat arrays + offset table */
    int *offsets = (int *)calloc(num_bins + 1, sizeof(int));
    if (!offsets) { free(bin_counts); Py_DECREF(mask_arr); return PyErr_NoMemory(); }
    for (int b = 0; b < num_bins; b++)
        offsets[b + 1] = offsets[b] + bin_counts[b];

    int total_binned = offsets[num_bins];
    double *bin_vals = (double *)malloc(total_binned * sizeof(double));
    int *bin_pix_idx = (int *)malloc(total_binned * sizeof(int));
    if (!bin_vals || !bin_pix_idx) {
        free(bin_counts); free(offsets);
        free(bin_vals); free(bin_pix_idx);
        Py_DECREF(mask_arr);
        return PyErr_NoMemory();
    }

    /* Fill bins (reuse bin_counts as write cursors) */
    memset(bin_counts, 0, num_bins * sizeof(int));
    for (Py_ssize_t i = 0; i < n; i++) {
        int b = bins[i];
        if (b >= 0 && b < num_bins) {
            int pos = offsets[b] + bin_counts[b];
            bin_vals[pos] = img[i];
            bin_pix_idx[pos] = (int)i;
            bin_counts[b]++;
        }
    }

    /* Phase 3: process each bin (parallel when OpenMP available) */
#ifdef _OPENMP
    {
        int nt = num_threads;
        if (nt <= 0) nt = omp_get_max_threads();
        omp_set_num_threads(nt);
    }
#endif
    /* Loop counter declared outside the for: MSVC's OpenMP 2.0 rejects
     * C99-style "for (int b = 0; ...)" inside #pragma omp for. */
    int b;
    #pragma omp parallel for schedule(dynamic)
    for (b = 0; b < num_bins; b++) {
        Py_ssize_t bsize = (Py_ssize_t)bin_counts[b];
        if (bsize < 3) continue;
        /* Each thread gets its own work buffer on the stack or heap */
        double *twork = (double *)malloc(bsize * sizeof(double));
        if (twork) {
            process_bin(
                bin_vals + offsets[b],
                bin_pix_idx + offsets[b],
                bsize, esdmul, use_median,
                twork, mask
            );
            free(twork);
        }
    }

    free(bin_counts);
    free(offsets);
    free(bin_vals);
    free(bin_pix_idx);

    return (PyObject *)mask_arr;
}


static PyMethodDef methods[] = {
    {"compute_outlier_mask_binned", compute_outlier_mask_binned, METH_VARARGS,
     "Compute outlier mask with equal-width binning.\n\n"
     "Args:\n"
     "    img: 1D float64 image array\n"
     "    bin_indices: 1D int32 bin index per pixel\n"
     "    num_bins: number of bins\n"
     "    esdmul: threshold in sigma/MAD units\n"
     "    use_median: True for median/MAD, False for mean/std\n"
     "    num_threads: max OpenMP threads (0 = all available, 1 = single-threaded)\n"},
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
