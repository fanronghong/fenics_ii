from xii.linalg.matrix_utils import is_number
from numpy.polynomial.legendre import leggauss
import numpy as np
from math import pi


# Some predefined shapes for surfaces averaging
class Cylinder(object):
    '''Obtain the shape by making a circle of radius r in the normal plane'''
    def __init__(self, radius, degree):
        # Make constant function
        if is_number(radius):
            assert radius > 0
            self.radius = lambda x0, r=radius: r
        # Then this must map points on centerline to radius
        else:
            self.radius = radius
        # NOTE: Let s by the arch length coordinate of the centerline of the 
        # cylinder. A tangent to 1d mesh at s is a normal to the plane in which
        # we draw a circle C(n, r) with radius r. For reduction of 3d we compute
        # 
        # |2*pi*R(s)|^-1\int_{C(n, r)} u dl =
        # 
        # |2*pi*R(s)|^-1\int_{-pi}^{pi} u(s + t1*R(s)*cos(theta) + t2*R(s)*sin(theta))R*d(theta) = 
        #
        # |2*pi*R(s)|^-1\int_{-1}^{1} u(s + t1*R(s)*cos(pi*t) + t2*R(s)*sin(pi*t))*pi*R*dt = 
        #
        # 1/2*sum_q u(s + t1*R(s)*cos(pi*x_q) + t2*R(s)*sin(pi*x_q))
        
        xq, wq = leggauss(degree)
        self.__weights__ = wq*0.5  # Scale down by 0.5

        # Precompute trigonometric part (only shift by tangents t1, t2)
        self.cos_xq = np.cos(np.pi*xq).reshape((-1, 1))
        self.sin_xq = np.sin(np.pi*xq).reshape((-1, 1))

    @property
    def weights(self):
        '''Quad weights'''
        return self.__weights__

    def points(self, n):
        '''Quad points for circle(x0, radius(x0)) in plane with normal n'''
        # Fix plane
        t1 = np.array([n[1]-n[2], n[2]-n[0], n[0]-n[1]])
    
        t2 = np.cross(n, t1)
        t1 = t1/np.linalg.norm(t1)
        t2 = t2/np.linalg.norm(t2)

        def pts(x0, me=self, t1=t1, t2=t2):
            rad = self.radius(x0)
            return x0 + rad*t1*me.sin_xq + rad*t2*me.cos_xq

        return pts

    def length(self, n):
        '''Length in plane with normal n'''
        # NOTE: Due to the cancellation above (wq is included in weight)
        # the length is 1 for the purpose of integration
        return lambda x: 1


class Ball(object):
    '''Reduce 3d to point by ball integration'''
    # Using quadpy, not all degrees are available -> missin JSON
    
    def __init__(self, radius, degree):
        # Make constant function
        if is_number(radius):
            assert radius > 0
            self.radius = lambda x0, r=radius: r
        # Then this must map points on centerline to radius
        else:
            self.radius = radius
            
        from quadpy.sphere import Lebedev

        integrator = Lebedev(str(degree))
        self.xq = integrator.points
        self.__weights__ = integrator.weights

    @property
    def weights(self):
        '''Quad weights'''
        return self.__weights__

    def points(self, n):
        '''Quad points for ball of radius r at x0'''
        def pts(x0, me=self):
            rad = self.radius(x0)
            return x0 + rad*self.xq
        return pts

    def length(self, n):
        '''Length in plane with normal n'''
        # NOTE: Due to the cancellation above (wq is included in weight)
        # the length is 1 for the purpose of integration
        return lambda x: 1


class SquareBox(object):
    '''
    Is specified by normal (will be given by 1d mesh) and functions:
    P(x\in R^3) -> R^3 the position of the ll corner
    '''
    # NOTE: we want (*) 1/|sq|*\int_{sq} f*dl, len e be the square edge
    # then (*) = 1/4/|e|*\sum_e \int_{e} f*dl
    #          = 1/4/|e|*\sum_e \int_{A}^B f*dl
    #          = 1/4/|e|*\sum_e \int_{-1}^1 f(0.5*A*(1-s)+0.5*B*(1+s))*(0.5*|e|)dl
    #           = 1/4 * \sum_e \sum_q 0.5*wq f(0.5*A*(1-sq)+0.5*B*(1+sq))
    #
    # In the API of shape_surface_averate 0.5*wq are weights,
    #                                     4 has the role of length
    #                                     xq are clear
    def __init__(self, P, degree):
        if isinstance(P, (tuple, list, np.ndarray)):
            assert all(is_number(Pi) for Pi in P)
            self.P = lambda x0, p=P: p
        else:
            self.P = P

        xq, wq = leggauss(degree)
        # Repeat for each edge
        self.__weights__ = 0.5*np.tile(wq, 4)
        self.__xq__ = xq  # Point for edge -1 -- 1
        
    @property
    def weights(self):
        '''Quad weights'''
        return self.__weights__

    def points(self, n):
        '''Quad points for square'''
        n = n/np.linalg.norm(n)

        def pts(x0, n=n, me=self):
            r = me.square(x0, n, me.P(x0))
            return me.square_xq(r)

        return pts

    def length(self, n):
        '''Length in plane with normal n'''
        # NOTE: Due to the cancellation above (wq is included in weight)
        # the length is 1 for the purpose of integration
        def circumnference(x0, n=n, me=self):
            return 4.
        return circumnference

    def square_xq(self, (A, B, C, D)):
        '''Quad points for rectangle A--B--D--D--'''
        xq = []
        for X, Y in zip((A, B, C, D), (B, C, D, A)):
            xq.extend([0.5*X*(1 - s) + 0.5*Y*(1 + s) for s in self.__xq__])
        return xq

    def square(self, x0, n, P):
        '''
        Make square with center x0 in plane with normal n and other 
        vertices obtained by rotating (P-x0)
        '''
        # n = n/np.linalg.norm(n)
        #  P_       Pr
        # 
        #      x0
        # P         P+
        vec = P - x0
        Pm = x0 + vec*np.cos(pi/2) + np.cross(n, vec)*np.sin(pi/2) + n*(n.dot(vec))*(1-np.cos(pi/2))
        Pr = x0 - (P-x0)
        Pp = x0 + vec*np.cos(3*pi/2) + np.cross(n, vec)*np.sin(3*pi/2) + n*(n.dot(vec))*(1-np.cos(3*pi/2))

        return (P, Pm, Pr, Pp)

# --------------------------------------------------------------------

if __name__ == '__main__':
    from mpl_toolkits.mplot3d import Axes3D
    import matplotlib.pyplot as plt

    size = 0.125
    sq = SquareBox(P=lambda x0: np.array([size*np.cos(0.5*pi*x0[2]),
                                          size*np.sin(0.5*pi*x0[2]),
                                          x0[2]]),
                   degree=8)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    n = np.array([0, 0, 1])

    f = lambda x: x[0]*x[0]
    
    pts = sq.points(n=n)
    length = sq.length(n=n)
    wq = sq.weights
    l = len(wq)/4
    
    for s in np.linspace(0, 2, 20):
        x0 = np.array([0.0, 0.0, s])
        x = np.row_stack(pts(x0))
        # print x
        # for i in range(4):
        #     # print x[i*l:(i+1)*l][0], x[i*l:(i+1)*l][-1]
        #     print 2*size*sum(f(xi)*wqi for xi, wqi in zip(x[i*l:(i+1)*l],
        #                                            wq[i*l:(i+1)*l]))
        # print
        
        ax.plot3D(x[:, 0], x[:, 1], x[:, 2], marker='o')

    # ----------------------

    radius = 0.125
    sq = Cylinder(radius=radius, degree=16)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    n = np.array([0, 0, 1])

    f = lambda x: x[0]*x[0]
    
    pts = sq.points(n=n)
    
    for s in np.linspace(0, 2, 20):
        x0 = np.array([0.0, 0.0, s])
        x = np.row_stack(pts(x0))
        ax.plot3D(x[:, 0], x[:, 1], x[:, 2], marker='o')

    plt.show()
