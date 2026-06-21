"""运管站货车审验 - 5 个 workflow popup 的处理函数

每个文件对应一个 popup,handle() 是统一入口。
"""
from popups.p1_vehicle_check import handle as handle_vehicle_check
from popups.p2_tech_review import handle as handle_tech_review
from popups.p3_business_review import handle as handle_business_review
from popups.p4_vehicle_annual import handle as handle_vehicle_annual
from popups.p5_archive import handle as handle_archive

__all__ = [
    "handle_vehicle_check",
    "handle_tech_review",
    "handle_business_review",
    "handle_vehicle_annual",
    "handle_archive",
]
