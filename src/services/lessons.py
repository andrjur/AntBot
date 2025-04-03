async def get_lesson_materials(course_id: str, lesson: int) -> list[dict]:
    """Получаем материалы урока с кешированием"""
    lesson_dir = Path(f"data/courses/{course_id}/lesson{lesson}")
    if not lesson_dir.exists():
        raise LessonNotFoundError(f"Урок {lesson} не найден")
    
    return sorted([
        {
            'type': get_file_type(file.name),
            'content': await file.read_text(),
            'file_path': str(file)
        }
        for file in lesson_dir.glob('*')
        if file.is_file()
    ], key=lambda x: x['file_path'])