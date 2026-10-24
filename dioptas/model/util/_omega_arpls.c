/* SPDX-License-Identifier: MIT
 * Independent CPU arPLS implementation from the equations in Baek et al.
 * DOI 10.1039/C4AN01061B. No background-sc or Stack Overflow code reused.
 * Each pixel has a banded Cholesky solve, O(frames) per reweighting step.
 * OpenMP only distributes independent pixels; reduction order per pixel is fixed.
 */
#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <numpy/arrayobject.h>
#include <math.h>
#include <stdlib.h>
#ifdef _OPENMP
#include <omp.h>
#endif

static int fit_row(const double *input, double *output, npy_intp n,
                   double lambda, double tolerance, int maximum,
                   double *work, int *steps) {
    double *y = work, *weights = y + n, *diag = weights + n;
    double *sub1 = diag + n, *sub2 = sub1 + n, *z = sub2 + n;
    double offset = input[0], scale = 0;
    for (npy_intp i = 0; i < n; ++i) {
        double delta = fabs(input[i] - offset);
        if (delta > scale) scale = delta;
    }
    *steps = 0;
    if (scale == 0) {
        for (npy_intp i = 0; i < n; ++i) output[i] = input[i];
        return 1;
    }
    for (npy_intp i = 0; i < n; ++i) {
        y[i] = (input[i] - offset) / scale;
        weights[i] = 1;
    }
    int converged = 0;
    for (int step = 0; step < maximum; ++step) {
        /* Lower Cholesky factor of W + lambda D^T D. The diagonal
         * coefficients are sums of squared entries of [1,-2,1]. */
        for (npy_intp i = 0; i < n; ++i) {
            double penalty = 0;
            if (i < n - 2) penalty += 1;
            if (i > 0 && i < n - 1) penalty += 4;
            if (i > 1) penalty += 1;
            sub2[i] = i > 1 ? lambda / diag[i - 2] : 0;
            double adjacent = i > 0 ? -2 * lambda * ((i < n - 1) + (i > 1)) : 0;
            sub1[i] = i > 0 ? (adjacent - sub2[i] * sub1[i - 1]) / diag[i - 1] : 0;
            double pivot = weights[i] + lambda * penalty - sub1[i] * sub1[i] - sub2[i] * sub2[i];
            if (!(pivot > 0) || !isfinite(pivot)) return -1;
            diag[i] = sqrt(pivot);
            double rhs = weights[i] * y[i];
            if (i > 0) rhs -= sub1[i] * z[i - 1];
            if (i > 1) rhs -= sub2[i] * z[i - 2];
            z[i] = rhs / diag[i];
        }
        for (npy_intp i = n; i-- > 0;) {
            double rhs = z[i];
            if (i + 1 < n) rhs -= sub1[i + 1] * z[i + 1];
            if (i + 2 < n) rhs -= sub2[i + 2] * z[i + 2];
            z[i] = rhs / diag[i];
        }
        *steps = step + 1;
        /* Welford variance avoids subtracting nearly equal second moments. */
        npy_intp count = 0;
        double mean = 0, variance_sum = 0, max_residual = 0;
        for (npy_intp i = 0; i < n; ++i) {
            double residual = y[i] - z[i];
            if (fabs(residual) > max_residual) max_residual = fabs(residual);
            if (residual < 0) {
                ++count;
                double delta = residual - mean;
                mean += delta / count;
                variance_sum += delta * (residual - mean);
            }
        }
        double sigma = count ? sqrt(fmax(0, variance_sum / count)) : 0;
        if (count < 2 || max_residual < 1e-10) {
            converged = 1;
            break;
        }
        sigma = fmax(sigma, 1e-8);
        double difference2 = 0, magnitude2 = 0;
        for (npy_intp i = 0; i < n; ++i) {
            double argument = 2 * (y[i] - z[i] - (2 * sigma - mean)) / sigma;
            argument = fmax(-40, fmin(40, argument));
            double next = fmax(1e-8, 1 / (1 + exp(argument)));
            double difference = next - weights[i];
            difference2 += difference * difference;
            magnitude2 += weights[i] * weights[i];
            weights[i] = next;
        }
        if (sqrt(difference2 / magnitude2) < tolerance) {
            converged = 1;
            break;
        }
    }
    for (npy_intp i = 0; i < n; ++i) output[i] = z[i] * scale + offset;
    return converged;
}

static PyObject *baselines(PyObject *self, PyObject *args) {
    PyObject *source;
    double lambda, tolerance;
    int maximum, workers;
    if (!PyArg_ParseTuple(args, "Oddii", &source, &lambda, &tolerance, &maximum, &workers)) return NULL;
    if (!isfinite(lambda) || lambda < 1e-6 || lambda > 1e9 ||
        !isfinite(tolerance) || tolerance <= 0 || tolerance >= 1 ||
        maximum < 1 || maximum > 1000 || workers < 1 || workers > 128) {
        PyErr_SetString(PyExc_ValueError, "Invalid arPLS parameters.");
        return NULL;
    }
    PyArrayObject *data = (PyArrayObject *)PyArray_FROM_OTF(source, NPY_DOUBLE, NPY_ARRAY_IN_ARRAY);
    if (!data) return NULL;
    if (PyArray_NDIM(data) != 2 || PyArray_DIM(data, 1) < 3) {
        Py_DECREF(data);
        PyErr_SetString(PyExc_ValueError, "Expected (pixels, frames >= 3).");
        return NULL;
    }
    npy_intp rows = PyArray_DIM(data, 0), n = PyArray_DIM(data, 1);
    const double *input = (double *)PyArray_DATA(data);
    for (npy_intp i = 0; i < PyArray_SIZE(data); ++i) {
        if (!isfinite(input[i])) {
            Py_DECREF(data);
            PyErr_SetString(PyExc_ValueError, "Input must be finite.");
            return NULL;
        }
    }
#ifndef _OPENMP
    workers = 1;
#endif
    if (rows > 0 && workers > rows) workers = (int)rows;
    PyArrayObject *output = (PyArrayObject *)PyArray_SimpleNew(2, PyArray_DIMS(data), NPY_DOUBLE);
    PyArrayObject *iterations = (PyArrayObject *)PyArray_SimpleNew(1, &rows, NPY_INT32);
    PyArrayObject *flags = (PyArrayObject *)PyArray_SimpleNew(1, &rows, NPY_BOOL);
    double *scratch = NULL;
    if (n <= NPY_MAX_INTP / (6 * workers * (npy_intp)sizeof(double)))
        scratch = (double *)calloc((size_t)workers * 6 * n, sizeof(double));
    if (!output || !iterations || !flags || !scratch) {
        Py_DECREF(data); Py_XDECREF(output); Py_XDECREF(iterations); Py_XDECREF(flags);
        free(scratch);
        return PyErr_NoMemory();
    }
    double *result = (double *)PyArray_DATA(output);
    npy_int32 *counts = (npy_int32 *)PyArray_DATA(iterations);
    npy_bool *converged = (npy_bool *)PyArray_DATA(flags);
    int failure = 0;
    /* MSVC's OpenMP 2.0 requires the induction variable to be declared
     * outside the parallel-for statement, as in the Spot Mask extension. */
    npy_intp row;
    Py_BEGIN_ALLOW_THREADS
#ifdef _OPENMP
    #pragma omp parallel for num_threads(workers) schedule(static) reduction(|:failure)
#endif
    for (row = 0; row < rows; ++row) {
        int worker = 0, steps = 0;
#ifdef _OPENMP
        worker = omp_get_thread_num();
#endif
        int status = fit_row(input + row * n, result + row * n, n, lambda, tolerance,
                             maximum, scratch + (npy_intp)worker * 6 * n, &steps);
        counts[row] = steps;
        converged[row] = status == 1;
        failure |= status < 0;
    }
    Py_END_ALLOW_THREADS
    free(scratch);
    Py_DECREF(data);
    if (failure) {
        Py_DECREF(output); Py_DECREF(iterations); Py_DECREF(flags);
        PyErr_SetString(PyExc_ArithmeticError, "arPLS system lost positive definiteness; reduce smoothness.");
        return NULL;
    }
    return Py_BuildValue("NNN", output, iterations, flags);
}

static PyMethodDef methods[] = {
    {"baselines", baselines, METH_VARARGS, "Fit arPLS baselines to contiguous pixel sequences."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "_omega_arpls", NULL, -1, methods};
PyMODINIT_FUNC PyInit__omega_arpls(void) {
    import_array();
    PyObject *m = PyModule_Create(&module);
    if (!m) return NULL;
#ifdef _OPENMP
    PyModule_AddIntConstant(m, "openmp_enabled", 1);
#else
    PyModule_AddIntConstant(m, "openmp_enabled", 0);
#endif
    return m;
}
