from agent_04_bom_duct import Agent04_DuctworkBOM
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM


class SwindBOMEngine:
    """
    Facade điều phối 3 Agent Bóc tách Định mức Cơ khí chuyên biệt (Multi-Workshop BOM Engine):
    - Agent 04 (Agent04_DuctworkBOM): Xưởng Ống gió, Phụ kiện ống, Khớp nối mềm Canvas, Hộp/Vách tiêu âm.
    - Agent 05 (Agent05_DamperBOM): Xưởng Van gió & Van PCCC EI (VCD, NRD, MD, FD, MFD Đơn cánh FSLF24V / Đa cánh BFN24).
    - Agent 06 (Agent06_DiffuserBOM): Xưởng Cửa gió & Miệng gió nhôm định hình (SWL, SEEG, SLB, SCD, SAG/DAG, SOBD, LCCT, Filter G4).
    """

    @staticmethod
    def get_duct_thickness(max_dim):
        return Agent04_DuctworkBOM.get_duct_thickness(max_dim)

    @staticmethod
    def calculate_duct_bom(parent_id, w, h, l=1120, brand="PN", flange_type="TDF", is_fitting=False, unit="m2", specified_thickness=None):
        return Agent04_DuctworkBOM.calculate_duct_bom(
            parent_id=parent_id,
            w=w,
            h=h,
            l=l,
            brand=brand,
            flange_type=flange_type,
            is_fitting=is_fitting,
            unit=unit,
            specified_thickness=specified_thickness
        )

    @staticmethod
    def calculate_canvas_bom(parent_id, w, h, l=200, brand="PN"):
        return Agent04_DuctworkBOM.calculate_canvas_bom(parent_id=parent_id, w=w, h=h, l=l, brand=brand)

    @staticmethod
    def calculate_acoustic_partition_bom(parent_id, w, h, l=1000, brand="PN", unit="Cái", include_casing=True):
        return Agent04_DuctworkBOM.calculate_acoustic_partition_bom(
            parent_id=parent_id,
            w=w,
            h=h,
            l=l,
            brand=brand,
            unit=unit,
            include_casing=include_casing
        )

    @staticmethod
    def calculate_damper_bom(parent_id, damper_type, w, h, brand="PN", ei_rating=0, mfd_mode="multi_bfn24"):
        return Agent05_DamperBOM.calculate_damper_bom(
            parent_id=parent_id,
            damper_type=damper_type,
            w=w,
            h=h,
            brand=brand,
            ei_rating=ei_rating,
            mfd_mode=mfd_mode
        )

    @staticmethod
    def calculate_diffuser_bom(parent_id, diffuser_type, w, h, profile_type="Z", has_obd=False, has_mesh=False, has_filter=False, is_double_layer=False, is_black_2nd_layer=False):
        return Agent06_DiffuserBOM.calculate_diffuser_bom(
            parent_id=parent_id,
            diffuser_type=diffuser_type,
            w=w,
            h=h,
            profile_type=profile_type,
            has_obd=has_obd,
            has_mesh=has_mesh,
            has_filter=has_filter,
            is_double_layer=is_double_layer,
            is_black_2nd_layer=is_black_2nd_layer
        )
