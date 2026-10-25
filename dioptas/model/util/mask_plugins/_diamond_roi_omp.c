/* Optional threaded backend shares the numerical implementation. A separate
 * translation unit keeps serial builds free of OpenMP startup/barrier costs. */
#define DIOPTAS_DIAMOND_OMP 1
#include "_diamond_roi_c.c"
