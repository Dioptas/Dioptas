/* SPDX-License-Identifier: MIT
 * Serial, portable C implementation: coarse discovery and bounded full-resolution
 * windows. No OpenMP, Python loops over pixels, or full-resolution image copy.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <numpy/arrayobject.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#define CAPSULE_NAME "dioptas.diamond_roi.v1"
typedef struct {
    int h,w,ch,cw,n,block,radius,min_area,min_radius,growth,max_work,exclude_zero,nranges;
    double seed,wing;
    double *angles,*ranges;
    float *pool,*smooth,*back,*a,*b,*stat,*roi,*filtered;
    uint8_t *valid,*seed_pixels,*opened,*distance;
    int *labels,*queue,*deque;
    double *integral;
    int stat_capacity,busy;
} Context;

typedef struct {
    const char *data,*mask;
    npy_intp sy,sx,my,mx;
    int type;
} Image;

static void release_context(Context *c) {
    if (!c) return;
    free(c->angles); free(c->ranges); free(c->pool); free(c->smooth);
    free(c->back); free(c->a); free(c->b); free(c->stat); free(c->roi);
    free(c->filtered); free(c->valid); free(c->seed_pixels); free(c->opened);
    free(c->distance); free(c->labels); free(c->queue); free(c->deque);
    free(c->integral); free(c);
}
static void destroy_context(PyObject *capsule) {
    release_context((Context*)PyCapsule_GetPointer(capsule,CAPSULE_NAME));
}

static PyObject *create_context(PyObject *self, PyObject *args) {
    PyObject *angle_obj,*range_obj;
    int h,w,block,radius,area,min_radius,growth,max_work,zero;
    double seed,wing;
    if (!PyArg_ParseTuple(args,"OO(ii)iiddiiiip",&angle_obj,&range_obj,&h,&w,
                          &block,&radius,&seed,&wing,&area,&min_radius,&growth,&max_work,&zero)) return NULL;
    if (h<1 || w<1 || h>INT_MAX/16 || w>INT_MAX/16 || (int64_t)h*w>INT_MAX/8 ||
        block<1 || block>64 || radius<1 || radius>INT_MAX/2 ||
        area<1 || area>INT_MAX/2 || min_radius<1 || min_radius>254 ||
        growth<0 || growth>254 || max_work<1 || max_work>INT_MAX/8 ||
        !isfinite(seed) || !isfinite(wing) || seed<=0 || wing<=0 || wing>seed) {
        PyErr_SetString(PyExc_ValueError,"Invalid native detector dimensions or settings"); return NULL;
    }
    PyArrayObject *angles=(PyArrayObject*)PyArray_FROM_OTF(angle_obj,NPY_DOUBLE,NPY_ARRAY_IN_ARRAY);
    PyArrayObject *ranges=(PyArrayObject*)PyArray_FROM_OTF(range_obj,NPY_DOUBLE,NPY_ARRAY_IN_ARRAY);
    if (!angles || !ranges) { Py_XDECREF(angles); Py_XDECREF(ranges); return NULL; }
    int ch=(h+block-1)/block,cw=(w+block-1)/block;
    if (PyArray_NDIM(angles)!=2 || PyArray_DIM(angles,0)!=ch || PyArray_DIM(angles,1)!=cw ||
        PyArray_NDIM(ranges)!=2 || PyArray_DIM(ranges,1)!=2 || PyArray_DIM(ranges,0)>1024) {
        Py_DECREF(angles); Py_DECREF(ranges);
        PyErr_SetString(PyExc_ValueError,"Invalid coarse geometry or diamond ranges"); return NULL;
    }
    Context *c=(Context*)calloc(1,sizeof(Context));
    if (!c) { Py_DECREF(angles); Py_DECREF(ranges); return PyErr_NoMemory(); }
    c->h=h;c->w=w;c->ch=ch;c->cw=cw;c->n=ch*cw;c->block=block;
    c->radius=(radius+block-1)/block;c->seed=seed;c->wing=wing;
    c->min_area=(area+block*block-1)/(block*block);c->min_radius=min_radius;c->growth=growth;
    c->max_work=max_work;c->exclude_zero=zero;c->nranges=(int)PyArray_DIM(ranges,0);
    c->stat_capacity=c->n>8*(h+w)?c->n:8*(h+w);
    int queue_capacity=max_work>c->n?max_work:c->n;
#define ALLOC(field,count,type) c->field=(type*)calloc((size_t)(count),sizeof(type)); if(!c->field) goto oom
    ALLOC(angles,c->n,double); ALLOC(ranges,c->nranges*2+1,double);
    ALLOC(pool,c->n,float); ALLOC(smooth,c->n,float); ALLOC(back,c->n,float);
    ALLOC(a,c->n,float); ALLOC(b,c->n,float); ALLOC(stat,c->stat_capacity,float);
    ALLOC(roi,max_work,float); ALLOC(filtered,max_work,float);
    ALLOC(valid,c->n,uint8_t); ALLOC(seed_pixels,c->n,uint8_t); ALLOC(opened,c->n,uint8_t);
    ALLOC(distance,max_work,uint8_t); ALLOC(labels,c->n,int);
    ALLOC(queue,queue_capacity,int); ALLOC(deque,(ch>cw?ch:cw),int);
    ALLOC(integral,(ch+1)*(cw+1),double);
#undef ALLOC
    memcpy(c->angles,PyArray_DATA(angles),c->n*sizeof(double));
    memcpy(c->ranges,PyArray_DATA(ranges),c->nranges*2*sizeof(double));
    Py_DECREF(angles);Py_DECREF(ranges);
    PyObject *capsule=PyCapsule_New(c,CAPSULE_NAME,destroy_context);
    if(!capsule)release_context(c);
    return capsule;
oom:
    Py_DECREF(angles);Py_DECREF(ranges);release_context(c);return PyErr_NoMemory();
}

static double read_pixel(const Image *im,int y,int x) {
    const char *p=im->data+y*im->sy+x*im->sx;
    switch(im->type) {
        case NPY_UINT16:return *(const uint16_t*)p;
        case NPY_UINT32:return *(const uint32_t*)p;
        case NPY_INT32:return *(const int32_t*)p;
        case NPY_FLOAT32:return *(const float*)p;
        default:return *(const double*)p;
    }
}
static int usable(const Image *im,int y,int x,double v,int exclude_zero) {
    return isfinite(v) && (!exclude_zero || v!=0) &&
           (!im->mask || !*(const npy_bool*)(im->mask+y*im->my+x*im->mx));
}

static void pool_image(Context *c,const Image *im) {
    int block=c->block;
    /* Specialize the inner pixel loop by dtype; preserve arbitrary row flips. */
#define POOL(TYPE) \
    for(int cy=0;cy<c->ch;cy++) for(int cx=0;cx<c->cw;cx++) { \
        double sum=0;int count=0; \
        int y1=(cy+1)*block<c->h?(cy+1)*block:c->h; \
        int x1=(cx+1)*block<c->w?(cx+1)*block:c->w; \
        for(int y=cy*block;y<y1;y++) { \
            const char *row=im->data+y*im->sy; \
            for(int x=cx*block;x<x1;x++) { \
                double v=*(const TYPE*)(row+x*im->sx); \
                if(usable(im,y,x,v,c->exclude_zero)) {sum+=v;count++;} \
            } \
        } \
        int i=cy*c->cw+cx;c->valid[i]=(count>0);c->pool[i]=count?(float)(sum/count):NAN; \
    }
    switch(im->type) {
        case NPY_UINT16:POOL(uint16_t);break;
        case NPY_UINT32:POOL(uint32_t);break;
        case NPY_INT32:POOL(int32_t);break;
        case NPY_FLOAT32:POOL(float);break;
        default:POOL(double);break;
    }
#undef POOL
}

/* O(n) clipped-window extrema, ignoring NaN (missing detector pixels). */
static void extreme_line(const float *src,float *dst,int n,int stride,int radius,int is_max,int *q) {
    int head=0,tail=0,right=0;
    for(int x=0;x<n;x++) {
        int end=x+radius<n?x+radius:n-1;
        while(right<=end) {
            float v=src[right*stride];
            if(isfinite(v)) {
                while(tail>head && (is_max?src[q[tail-1]*stride]<=v:src[q[tail-1]*stride]>=v))tail--;
                q[tail++]=right;
            }
            right++;
        }
        while(tail>head && q[head]<x-radius)head++;
        dst[x*stride]=tail>head?src[q[head]*stride]:NAN;
    }
}
static void extreme(Context *c,const float *src,float *dst,int is_max,int vertical) {
    if(vertical) for(int x=0;x<c->cw;x++)
        extreme_line(src+x,dst+x,c->ch,c->cw,c->radius,is_max,c->deque);
    else for(int y=0;y<c->ch;y++)
        extreme_line(src+y*c->cw,dst+y*c->cw,c->cw,1,c->radius,is_max,c->deque);
}
static void smooth_grid(Context *c) {
    for(int y=0;y<c->ch;y++)for(int x=0;x<c->cw;x++) {
        double sum=0,weight=0;
        for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
            int yy=y+dy,xx=x+dx;
            if(yy<0||yy>=c->ch||xx<0||xx>=c->cw)continue;
            int j=yy*c->cw+xx;
            if(c->valid[j]) {int w=(dy==0?2:1)*(dx==0?2:1);sum+=w*c->pool[j];weight+=w;}
        }
        c->smooth[y*c->cw+x]=weight?(float)(sum/weight):NAN;
    }
}
static float select_rank(float *a,int n,int k) {
    int lo=0,hi=n-1;
    while(lo<hi) {
        float pivot=a[(lo+hi)/2];int i=lo,j=hi;
        while(i<=j) {
            while(a[i]<pivot)i++;
            while(a[j]>pivot)j--;
            if(i<=j){float t=a[i];a[i]=a[j];a[j]=t;i++;j--;}
        }
        if(k<=j)hi=j;else if(k>=i)lo=i;else break;
    }
    return a[k];
}
static float select_median(float *a,int n) {return select_rank(a,n,n/2);}
static void make_seeds(Context *c) {
    int count=0;
    for(int i=0;i<c->n;i++)if(c->valid[i])c->stat[count++]=fabsf(c->pool[i]-c->smooth[i]);
    float global=count?select_median(c->stat,count)*1.4826f:0;
    if(global<0.01f)global=0.01f;
    int iw=c->cw+1;
    memset(c->integral,0,(size_t)(c->ch+1)*iw*sizeof(double));
    for(int y=0;y<c->ch;y++) {
        double sum=0;
        for(int x=0;x<c->cw;x++) {
            int i=y*c->cw+x;
            float v=c->valid[i]?fabsf(c->pool[i]-c->smooth[i]):0;
            sum+=fminf(v,global*3);
            c->integral[(y+1)*iw+x+1]=sum+c->integral[y*iw+x+1];
        }
    }
    for(int y=0;y<c->ch;y++)for(int x=0;x<c->cw;x++) {
        int y0=y>2?y-2:0,y1=y+3<c->ch?y+3:c->ch;
        int x0=x>2?x-2:0,x1=x+3<c->cw?x+3:c->cw;
        double sum=c->integral[y1*iw+x1]-c->integral[y0*iw+x1]-c->integral[y1*iw+x0]+c->integral[y0*iw+x0];
        double noise=fmax(global*.25,1.4826*sum/((x1-x0)*(y1-y0)));
        int i=y*c->cw+x;
        c->seed_pixels[i]=c->valid[i] && isfinite(c->back[i]) && c->smooth[i]>c->back[i]+c->seed*noise;
    }
    /* A 3x3 opening removes narrow arcs before labelling, including thin
       appendages attached to a broad seed. */
    memset(c->opened,0,c->n);
    for(int y=1;y<c->ch-1;y++)for(int x=1;x<c->cw-1;x++) {
        int all=1;
        for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)if(!c->seed_pixels[(y+dy)*c->cw+x+dx])all=0;
        if(all)for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)c->opened[(y+dy)*c->cw+x+dx]=1;
    }
}

static int solve_plane(double m[3][3],double v[3],double out[3]) {
    double a[3][4];
    for(int r=0;r<3;r++){for(int col=0;col<3;col++)a[r][col]=m[r][col];a[r][3]=v[r];}
    for(int col=0;col<3;col++) {
        int pivot=col;for(int r=col+1;r<3;r++)if(fabs(a[r][col])>fabs(a[pivot][col]))pivot=r;
        if(fabs(a[pivot][col])<1e-12)return 0;
        for(int k=col;k<4;k++){double t=a[pivot][k];a[pivot][k]=a[col][k];a[col][k]=t;}
        double divisor=a[col][col];for(int k=col;k<4;k++)a[col][k]/=divisor;
        for(int r=0;r<3;r++)if(r!=col){double q=a[r][col];for(int k=col;k<4;k++)a[r][k]-=q*a[col][k];}
    }
    for(int r=0;r<3;r++)out[r]=a[r][3];return 1;
}

static int process_roi(Context *c,const Image *im,npy_bool *out,int id,int x0,int x1,int y0,int y1,int *work) {
    int w=x1-x0,h=y1-y0,n=w*h;
    if(n>c->max_work || *work>c->max_work-n)return -1;
    *work+=n;
    for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
        double v=read_pixel(im,y+y0,x+x0);
        c->roi[y*w+x]=usable(im,y+y0,x+x0,v,c->exclude_zero)?(float)v:NAN;
    }
    int ns=0;
    for(int y=0;y<h;y++)for(int x=0;x<w;x++)
        if((x<2||y<2||x>=w-2||y>=h-2)&&isfinite(c->roi[y*w+x]))c->stat[ns++]=c->roi[y*w+x];
    if(ns<12)return 0;
    double plane[3]={select_median(c->stat,ns),0,0};
    for(int i=0;i<ns;i++)c->stat[i]=fabsf(c->stat[i]-(float)plane[0]);
    double sigma=fmax(select_median(c->stat,ns)*1.4826,0.01);
    for(int iteration=0;iteration<3;iteration++) {
        double m[3][3]={{0}},v[3]={0};int used=0;
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)if(x<2||y<2||x>=w-2||y>=h-2) {
            float value=c->roi[y*w+x];double u=(2.0*x-w+1)/w,t=(2.0*y-h+1)/h;
            if(!isfinite(value)||fabs(value-plane[0]-plane[1]*u-plane[2]*t)>3*sigma)continue;
            double p[3]={1,u,t};used++;
            for(int a=0;a<3;a++){v[a]+=p[a]*value;for(int b=0;b<3;b++)m[a][b]+=p[a]*p[b];}
        }
        if(used<12||!solve_plane(m,v,plane))break;
        ns=0;
        for(int y=0;y<h;y++)for(int x=0;x<w;x++)if(x<2||y<2||x>=w-2||y>=h-2) {
            float value=c->roi[y*w+x];double u=(2.0*x-w+1)/w,t=(2.0*y-h+1)/h;
            if(isfinite(value))c->stat[ns++]=(float)fabs(value-plane[0]-plane[1]*u-plane[2]*t);
        }
        sigma=fmax(select_median(c->stat,ns)*1.4826,0.01);
    }
    /* A step in illumination has a bright side continuing to the window's
       border. Require the smoothed seed to rise above that high-side residual,
       after removing the fitted gradient, rather than accepting the step. */
    ns=0;
    for(int y=0;y<h;y++)for(int x=0;x<w;x++)if(x<2||y<2||x>=w-2||y>=h-2) {
        float value=c->roi[y*w+x];
        double bg=plane[0]+plane[1]*(2.0*x-w+1)/w+plane[2]*(2.0*y-h+1)/h;
        if(isfinite(value))c->stat[ns++]=(float)(value-bg);
    }
    double high_border=select_rank(c->stat,ns,(int)((int64_t)(ns-1)*9/10)),peak=-INFINITY;
    for(int cy=y0/c->block;cy<(y1+c->block-1)/c->block;cy++)
        for(int cx=x0/c->block;cx<(x1+c->block-1)/c->block;cx++) {
            int p=cy*c->cw+cx;
            if(c->labels[p]!=id)continue;
            double x=(cx+.5)*c->block-x0,y=(cy+.5)*c->block-y0;
            double bg=plane[0]+plane[1]*(2*x-w+1)/w+plane[2]*(2*y-h+1)/h;
            peak=fmax(peak,c->smooth[p]-bg);
        }
    if(peak<=high_border+c->seed*sigma)return 0;
    for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
        double sum=0,weight=0;
        for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
            int yy=y+dy,xx=x+dx;
            if(yy<0||yy>=h||xx<0||xx>=w)continue;
            float value=c->roi[yy*w+xx];
            if(isfinite(value)){int v=(dy==0?2:1)*(dx==0?2:1);sum+=value*v;weight+=v;}
        }
        c->filtered[y*w+x]=weight?(float)(sum/weight):NAN;
    }
    /* Pooling broadens a very bright, narrow spike. Verify width again at
       detector resolution. The square-distance test requires an interior of
       min_radius pixels above local contrast and 1% of the seed's peak excess.
       It does not infer a saturated peak's missing intensity. */
    double width_level=fmax(c->seed*sigma,peak*.01);
    for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
        int p=y*w+x;
        double bg=plane[0]+plane[1]*(2.0*x-w+1)/w+plane[2]*(2.0*y-h+1)/h;
        int d=0;
        if(isfinite(c->roi[p])&&c->filtered[p]>bg+width_level) {
            d=c->min_radius;
            if(x==0||y==0)d=1;
            else {
                if(c->distance[p-1]<d)d=c->distance[p-1];
                if(c->distance[p-w]<d)d=c->distance[p-w];
                if(c->distance[p-w-1]<d)d=c->distance[p-w-1];
                if(x+1<w&&c->distance[p-w+1]<d)d=c->distance[p-w+1];
                if(d<c->min_radius)d++;
            }
        }
        c->distance[p]=(uint8_t)d;
    }
    int wide=0;
    for(int y=h-1;y>=0;y--)for(int x=w-1;x>=0;x--) {
        int p=y*w+x,d=c->distance[p];
        if(d>0) {
            if(x==w-1||y==h-1)d=1;
            else {
                int m=c->distance[p+1];
                if(c->distance[p+w]<m)m=c->distance[p+w];
                if(c->distance[p+w+1]<m)m=c->distance[p+w+1];
                if(x>0&&c->distance[p+w-1]<m)m=c->distance[p+w-1];
                if(m+1<d)d=m+1;
            }
        }
        c->distance[p]=(uint8_t)d;
        if(d>=c->min_radius&&c->labels[((y+y0)/c->block)*c->cw+(x+x0)/c->block]==id)wide=1;
    }
    if(!wide)return 0;
    memset(c->distance,255,n);int head=0,tail=0;
    for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
        int cy=(y+y0)/c->block,cx=(x+x0)/c->block,p=y*w+x;
        double bg=plane[0]+plane[1]*(2.0*x-w+1)/w+plane[2]*(2.0*y-h+1)/h;
        if(c->labels[cy*c->cw+cx]==id&&isfinite(c->roi[p])&&c->filtered[p]>bg+c->seed*sigma)
            {c->distance[p]=0;c->queue[tail++]=p;}
    }
    while(head<tail) {
        int p=c->queue[head++],y=p/w,x=p%w;
        out[(y+y0)*c->w+x+x0]=1;
        if(c->distance[p]>=c->growth)continue;
        int neighbors[4]={p-1,p+1,p-w,p+w};
        int allowed[4]={x>0,x+1<w,y>0,y+1<h};
        for(int k=0;k<4;k++)if(allowed[k]) {
            int q=neighbors[k],yy=q/w,xx=q%w;
            double bg=plane[0]+plane[1]*(2.0*xx-w+1)/w+plane[2]*(2.0*yy-h+1)/h;
            if(c->distance[q]==255&&isfinite(c->roi[q])&&c->filtered[q]>bg+c->wing*sigma) {
                c->distance[q]=(uint8_t)(c->distance[p]+1);c->queue[tail++]=q;
            }
        }
    }
    return 1;
}

static int run_detector(Context *c,const Image *im,npy_bool *out,int *accepted,int *work) {
    *accepted=0;*work=0;
    if(c->nranges==0)return 0;
    pool_image(c,im);smooth_grid(c);
    extreme(c,c->smooth,c->a,0,0);extreme(c,c->a,c->b,0,1);
    extreme(c,c->b,c->a,1,0);extreme(c,c->a,c->back,1,1);
    make_seeds(c);memset(c->labels,0,c->n*sizeof(int));int id=0;
    /* First label all seeds. The ROI queue reuses storage, so consume a
       component completely before starting its full-resolution window. */
    for(int start=0;start<c->n;start++)if(c->opened[start]&&!c->labels[start]) {
        id++;int head=0,tail=0;c->queue[tail++]=start;c->labels[start]=id;
        int minx=c->cw,maxx=0,miny=c->ch,maxy=0;double total=0,moment=0;
        while(head<tail) {
            int p=c->queue[head++],y=p/c->cw,x=p%c->cw;
            if(x<minx)minx=x;if(x>maxx)maxx=x;if(y<miny)miny=y;if(y>maxy)maxy=y;
            double weight=fmax(c->smooth[p]-c->back[p],0);
            if(isfinite(c->angles[p])){total+=weight;moment+=weight*c->angles[p];}
            int neighbors[4]={p-1,p+1,p-c->cw,p+c->cw};
            int allowed[4]={x>0,x+1<c->cw,y>0,y+1<c->ch};
            for(int k=0;k<4;k++)if(allowed[k]) {
                int q=neighbors[k];if(c->opened[q]&&!c->labels[q]){c->labels[q]=id;c->queue[tail++]=q;}
            }
        }
        if(tail<c->min_area||total<=0)continue;
        double angle=moment/total;int in_band=0;
        for(int k=0;k<c->nranges;k++)if(angle>=c->ranges[k*2]&&angle<=c->ranges[k*2+1])in_band=1;
        if(!in_band)continue;
        int x0=minx*c->block-c->growth,y0=miny*c->block-c->growth;
        int x1=(maxx+1)*c->block+c->growth,y1=(maxy+1)*c->block+c->growth;
        if(x0<0)x0=0;if(y0<0)y0=0;if(x1>c->w)x1=c->w;if(y1>c->h)y1=c->h;
        int result=process_roi(c,im,out,id,x0,x1,y0,y1,work);
        if(result<0)return -1;
        *accepted+=result;
    }
    return 0;
}

static PyObject *compute(PyObject *self,PyObject *args) {
    PyObject *capsule,*image_obj,*mask_obj=Py_None;
    if(!PyArg_ParseTuple(args,"OO|O",&capsule,&image_obj,&mask_obj))return NULL;
    Context *c=(Context*)PyCapsule_GetPointer(capsule,CAPSULE_NAME);if(!c)return NULL;
    if(c->busy){PyErr_SetString(PyExc_RuntimeError,"Native detector context is already in use");return NULL;}
    PyArrayObject *image=(PyArrayObject*)PyArray_FROM_O(image_obj),*mask=NULL;
    if(!image)return NULL;
    int type=PyArray_TYPE(image);
    if(PyArray_NDIM(image)!=2||PyArray_DIM(image,0)!=c->h||PyArray_DIM(image,1)!=c->w||
       !PyArray_ISALIGNED(image)||!PyArray_ISNOTSWAPPED(image)||
       !(type==NPY_UINT16||type==NPY_UINT32||type==NPY_INT32||type==NPY_FLOAT32||type==NPY_FLOAT64)) {
        Py_DECREF(image);PyErr_SetString(PyExc_ValueError,"Expected aligned native-endian uint16/uint32/int32/float32/float64 image with prepared shape");return NULL;
    }
    if(mask_obj!=Py_None) {
        mask=(PyArrayObject*)PyArray_FROM_OTF(mask_obj,NPY_BOOL,NPY_ARRAY_ALIGNED);
        if(!mask){Py_DECREF(image);return NULL;}
        if(PyArray_NDIM(mask)!=2||PyArray_DIM(mask,0)!=c->h||PyArray_DIM(mask,1)!=c->w) {
            Py_DECREF(image);Py_DECREF(mask);PyErr_SetString(PyExc_ValueError,"Mask shape mismatch");return NULL;
        }
    }
    npy_intp dims[2]={c->h,c->w};
    PyArrayObject *out=(PyArrayObject*)PyArray_ZEROS(2,dims,NPY_BOOL,0);
    if(!out){Py_DECREF(image);Py_XDECREF(mask);return NULL;}
    Image im={PyArray_DATA(image),mask?PyArray_DATA(mask):NULL,
              PyArray_STRIDE(image,0),PyArray_STRIDE(image,1),
              mask?PyArray_STRIDE(mask,0):0,mask?PyArray_STRIDE(mask,1):0,type};
    int status,accepted,work;
    c->busy=1;
    Py_BEGIN_ALLOW_THREADS
    status=run_detector(c,&im,(npy_bool*)PyArray_DATA(out),&accepted,&work);
    Py_END_ALLOW_THREADS
    c->busy=0;
    Py_DECREF(image);Py_XDECREF(mask);
    if(status<0){Py_DECREF(out);PyErr_SetString(PyExc_RuntimeError,"Diamond ROI work limit exceeded; no complete mask returned");return NULL;}
    return Py_BuildValue("Nii",out,accepted,work);
}
static PyMethodDef methods[]={
    {"create",create_context,METH_VARARGS,"Prepare reusable detector scratch and coarse geometry."},
    {"compute",compute,METH_VARARGS,"Detect diamond candidates; return owned mask, ROI count, visited window pixels."},
    {NULL,NULL,0,NULL}
};
static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"_diamond_roi_c",NULL,-1,methods};
PyMODINIT_FUNC PyInit__diamond_roi_c(void){import_array();return PyModule_Create(&module);}
