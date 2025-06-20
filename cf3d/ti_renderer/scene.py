import taichi as ti

from ti_renderer.math_utils import np_normalize
from ti_renderer.renderer import Renderer

VOXEL_DX = 1 / 16
SCREEN_RES = (1280, 720)
UP_DIR = (0, 1, 0)


MAT_LAMBERTIAN = 1
MAT_LIGHT = 2


class Scene:
    def __init__(self, voxel_edges=0.06, exposure=3, image_res=SCREEN_RES, up=UP_DIR):
        self.renderer = Renderer(
            dx=VOXEL_DX,
            image_res=image_res,
            up=up,
            voxel_edges=voxel_edges,
            exposure=exposure,
        )

    @staticmethod
    @ti.func
    def round_idx(idx_):
        idx = ti.cast(idx_, ti.f32)
        return ti.Vector([ti.round(idx[0]), ti.round(idx[1]), ti.round(idx[2])]).cast(
            ti.i32
        )

    @ti.func
    def set_voxel(self, idx, mat, color):
        self.renderer.set_voxel(self.round_idx(idx), mat, color)

    @ti.func
    def get_voxel(self, idx):
        mat, color = self.renderer.get_voxel(self.round_idx(idx))
        return mat, color

    def set_floor(self, height, color):
        self.renderer.floor_height[None] = height
        self.renderer.floor_color[None] = color

    def set_directional_light(self, direction, direction_noise, color):
        self.renderer.set_directional_light(direction, direction_noise, color)

    def set_background_color(self, color):
        self.renderer.background_color[None] = color

    def set_camera_pos(self, pos):
        self.renderer.set_camera_pos(*pos)

    def set_look_at(self, look_at):
        self.renderer.set_look_at(*look_at)

    def set_up(self, up):
        self.renderer.set_up(*up)

    def set_fov(self, fov):
        self.renderer.set_fov(fov)

    def finish(self):
        self.renderer.recompute_bbox()
