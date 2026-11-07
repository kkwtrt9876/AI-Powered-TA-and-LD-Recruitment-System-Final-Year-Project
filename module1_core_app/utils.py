import os
import datetime
from werkzeug.utils import secure_filename

def create_student_folder(student_id, course_name):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{secure_filename(student_id)}_{secure_filename(course_name)}_{timestamp}"
    base_path = "submissions"
    full_path = os.path.join(base_path, folder_name)
    
    if not os.path.exists(full_path):
        os.makedirs(full_path)
        
    return full_path

def save_text_file(folder, filename, content):
    path = os.path.join(folder, filename)
    with open(path, "w", encoding='utf-8') as f:
        f.write(content)

def save_file(folder, filename, file_obj):
    path = os.path.join(folder, filename)
    file_obj.save(path)
