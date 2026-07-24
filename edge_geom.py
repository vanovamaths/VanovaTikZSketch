
from __future__ import annotations
import math
from typing import List, Tuple

Point = Tuple[float, float]


def control_point(p0: Point, p1: Point, bend: float) -> Point:
    if not bend:
        return ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return p0
    nx, ny = -dy / length, dx / length  # unit normal
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    push = bend * 0.5 * length
    return (mx + nx * push, my + ny * push)


def quad_to_cubic(p0: Point, q: Point, p1: Point) -> Tuple[Point, Point]:

    c1 = (p0[0] + 2.0 / 3.0 * (q[0] - p0[0]), p0[1] + 2.0 / 3.0 * (q[1] - p0[1]))
    c2 = (p1[0] + 2.0 / 3.0 * (q[0] - p1[0]), p1[1] + 2.0 / 3.0 * (q[1] - p1[1]))
    return c1, c2


def point_on_quad(t: float, p0: Point, q: Point, p1: Point) -> Point:
    mt = 1 - t
    x = mt * mt * p0[0] + 2 * mt * t * q[0] + t * t * p1[0]
    y = mt * mt * p0[1] + 2 * mt * t * q[1] + t * t * p1[1]
    return (x, y)


def tangent_on_quad(t: float, p0: Point, q: Point, p1: Point) -> Point:
   
    dx = 2 * (1 - t) * (q[0] - p0[0]) + 2 * t * (p1[0] - q[0])
    dy = 2 * (1 - t) * (q[1] - p0[1]) + 2 * t * (p1[1] - q[1])
    return (dx, dy)


def sample_edge(p0: Point, p1: Point, bend: float, n: int = 24) -> List[Point]:
    """Polyline approximation of the edge (straight if bend==0), used for
    hit-testing / partial erasing so a curved arrow erases along its real
    visual path rather than the straight chord."""
    if not bend:
        return [(p0[0] + (p1[0] - p0[0]) * i / (n - 1),
                 p0[1] + (p1[1] - p0[1]) * i / (n - 1)) for i in range(n)]
    q = control_point(p0, p1, bend)
    return [point_on_quad(i / (n - 1), p0, q, p1) for i in range(n)]


def chord_normal(p0: Point, p1: Point) -> Point:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy) or 1.0
    return (-dy / length, dx / length)


def parallel_endpoints(p0: Point, p1: Point, offset: float) -> Tuple[Point, Point]:
    
    nx, ny = chord_normal(p0, p1)
    dx, dy = nx * offset, ny * offset
    return (p0[0] + dx, p0[1] + dy), (p1[0] + dx, p1[1] + dy)
