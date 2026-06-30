from views import results as results_view


_SCHED = {
    "assignments": [
        {
            "course_code": "ADA 110",
            "course_name": "Introduction to Data Analytics",
            "cohort": "ADA-1",
            "dept": "ADA",
            "department": "Analytics and Data Science",
            "instructor_name": "Ada Lovelace",
            "instructor_id": "ada@example.edu",
        },
        {
            "course_code": "ADA 110",
            "course_name": "Introduction to Data Analytics",
            "cohort": "ADA-2",
            "dept": "ADA",
            "department": "Analytics and Data Science",
        },
        {
            "course_code": "ARCH 312",
            "course_name": "",
            "cohort": "ARCH-3",
            "dept": "ARCH",
            "department": "",
        },
    ]
}


def test_result_entity_labels_include_department_and_course_names():
    dept_fmt = results_view._entity_label_func(_SCHED, "cohort")
    course_fmt = results_view._entity_label_func(_SCHED, "course_code")

    assert dept_fmt("ADA-1") == "ADA-1 · Analytics and Data Science"
    assert dept_fmt("ARCH-3") == "ARCH-3"
    assert course_fmt("ADA 110") == "ADA 110 · Introduction to Data Analytics"
    assert course_fmt("ARCH 312") == "ARCH 312"


def test_result_entity_labels_keep_instructor_email_format():
    fmt = results_view._entity_label_func(_SCHED, "instructor_name")

    assert fmt("Ada Lovelace") == "Ada Lovelace (ada@example.edu)"
