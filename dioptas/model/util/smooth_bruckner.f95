subroutine smooth_bruckner(y_bkg, y, n, smooth_points, iterations)
!     extracts a background of pattern/pattern by using an
!     intelligent moving average filter. Whereby for each point it is
!     checked whether the y-value is larger than the average - if it is
!     it will be replaced by the local average

!     y_bkg: is the output array with size n
!     y: is the input array with size n
!     smooth_points: are the half of the window size for averaging
!     iterations: number of iterations of running the algorithm
implicit none

integer, intent(in) :: n
integer, intent(in) :: smooth_points
integer, intent(in) :: iterations
double precision, intent(in), dimension(0:n-1) :: y
double precision, intent(out), dimension(0:n-1) :: y_bkg

double precision, dimension(0:n+2*smooth_points-1) :: y_extended

double precision :: window_avg
double precision :: y_new 
integer :: i, j
double precision :: window_size

! creating an extended y with having size n + 2*smooth_points
y_extended(0:smooth_points-1) = y(0)
y_extended(smooth_points:n+smooth_points-1) = y
y_extended(smooth_points+n:2*smooth_points+n-1) = y(n-1)

! actual algorithm:
window_size = 2*smooth_points + 1
do j=0, iterations-1
    window_avg = sum(y_extended(0:2*smooth_points))/(2*smooth_points+1)
    do i=smooth_points, (n-smooth_points-3) 
        if (y_extended(i)>window_avg) then
            y_new = window_avg        
!             updating central value in average (first bracket)
!             and shifting average by one index (second bracket)
            window_avg = window_avg + ((window_avg-y_extended(i)) + &
                                       (y_extended(i+smooth_points+1)-y_extended(i - smooth_points))) &
                                    /window_size
            y_extended(i) = y_new
        else
!             shifting average by one index
            window_avg = window_avg + (y_extended(i+smooth_points+1)-y_extended(i - smooth_points))/window_size
        end if 
    end do
end do

y_bkg = y_extended(smooth_points:n+smooth_points-1)
end subroutine