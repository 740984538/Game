"""商店场景 - 对应文档 §3.2.3"""
from __future__ import annotations
from src.scenes.base_scene import BaseScene


class ShopScene(BaseScene):
    """商店界面：展示商品，消耗金币购买遗物/卡牌/消耗品"""

    def enter(self, shop_type: str = "normal", **kwargs) -> None:
        # TODO: 根据 shop_type 生成商品列表
        pass

    def update(self, dt: float) -> None:
        # TODO: 处理购买逻辑
        pass

    def render(self, surface) -> None:
        # TODO: 渲染商店UI
        pass
