subroutine smooth_bruckner(y_bkg, y, n, smooth_points, iterations)
implicit none

integer, intent(in) :: n
integer, intent(in) :: smooth_points
integer, intent(in) :: iterations
double precision, intent(in), dimension(0:n-1) :: y
double precision, intent(out), dimension(0:n-1) :: y_bkg

double precision, dimension(0:n+2*smooth_points-1) :: y_extended

double precision :: y_avg
double precision :: window_avg
double precision :: y_new 
integer :: i, j
double precision :: window_size

double precision :: y_cutoff


y_extended(0:smooth_points-1) = y(0)
y_extended(smooth_points:n+smooth_points-1) = y
y_extended(smooth_points+n:2*smooth_points+n-1) = y(n-1)

y_avg = sum(y_extended)/size(y_extended)
y_cutoff = y_avg + 2 * (y_avg - minval(y_extended))


do i=0, size(y_extended)-1
    if (y_extended(i)>y_cutoff) then
        y_extended(i) = y_cutoff
    end if
end do

window_size = 2*smooth_points + 1

do j=0, iterations-1
    window_avg = sum(y_extended(0:2*smooth_points))/(2*smooth_points+1)
    do i=smooth_points, (n-smooth_points-3) 
        if (y_extended(i)>window_avg) then
            y_new = window_avg        
            window_avg = window_avg + ((window_avg-y_extended(i)) + &
                                       (y_extended(i+smooth_points+1)-y_extended(i - smooth_points))) &
                                    /window_size
            y_extended(i) = y_new
        else
            window_avg = window_avg + (y_extended(i+smooth_points+1)-y_extended(i - smooth_points))/window_size
        end if 
    end do
end do

y_bkg = y_extended(smooth_points:n+smooth_points-1)
end subroutine