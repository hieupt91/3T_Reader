import os
from pathlib import Path

def generate_source_code_document():
    project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_file = project_root / "docs" / "SOURCE_CODE_COPYRIGHT.txt"
    
    # Priority directories to include in the copyright registration
    target_dirs = ["app", "packages", "core"]
    
    # Collect files
    python_files = []
    for d in target_dirs:
        dir_path = project_root / d
        if dir_path.exists():
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.endswith(".py") and file != "__init__.py":
                        python_files.append(os.path.join(root, file))
    
    # Sort files to have a consistent output
    python_files.sort()
    
    with open(output_file, "w", encoding="utf-8") as out:
        out.write("MÃ NGUỒN PHẦN MỀM 3T READER\n")
        out.write("=" * 50 + "\n\n")
        
        for file_path in python_files:
            try:
                rel_path = os.path.relpath(file_path, project_root)
                out.write(f"\n{'='*50}\n")
                out.write(f"FILE: {rel_path}\n")
                out.write(f"{'='*50}\n\n")
                
                with open(file_path, "r", encoding="utf-8") as f:
                    out.write(f.read())
                    out.write("\n")
            except Exception as e:
                print(f"Lỗi khi đọc file {file_path}: {e}")
                
    print(f"Đã xuất toàn bộ mã nguồn ra file: {output_file}")
    print("Vui lòng in file này (thường in 50 trang đầu và 50 trang cuối nếu mã nguồn quá dài) để nộp hồ sơ Bản quyền.")

if __name__ == "__main__":
    generate_source_code_document()
