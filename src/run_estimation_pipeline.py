import os
from datetime import datetime
from swind_master_runner import resolve_path, get_latest_file, load_master_data, run_master_pipeline

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
BOQ_FILE = resolve_path("input/Haus_Dalat_BOQ_MEP (NCC).xlsx")

base_name = os.path.basename(BOQ_FILE)
project_name = base_name.replace("_BOQ_MEP (NCC).xlsx", "").replace(".xlsx", "").strip()
project_dir = resolve_path(f"data/projects/{project_name}")
os.makedirs(project_dir, exist_ok=True)

MASTER_DATA_TECH_JSON = resolve_path("data/master_data/master_database_tech.json")
MASTER_DATA_PRICE_JSON = resolve_path("data/master_data/master_database_price.json")
OUTPUT_WORKBOOK = os.path.join(project_dir, f"{project_name}_ESTIMATION_{timestamp}.xlsx")
QA_REPORT_PATH = os.path.join(project_dir, f"QA_Audit_Report_{timestamp}.json")


def run_pipeline(boq_file=None):
    target_boq = resolve_path(boq_file) if boq_file else BOQ_FILE
    run_master_pipeline(
        boq_file=target_boq,
        sheet_names=["DHKK"],
        interactive=False,
        auto_accept=True
    )


if __name__ == "__main__":
    run_pipeline()
