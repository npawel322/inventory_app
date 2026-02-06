from django.db import migrations, models


def merge_departments_by_name(apps, schema_editor):
    Department = apps.get_model("inventory", "Department")
    DepartmentPosition = apps.get_model("inventory", "DepartmentPosition")

    canonical_by_name = {}
    for dep in Department.objects.order_by("name", "id"):
        canonical = canonical_by_name.get(dep.name)
        if canonical is None:
            canonical_by_name[dep.name] = dep
            continue

        used_numbers = set(
            DepartmentPosition.objects.filter(department_id=canonical.id).values_list("number", flat=True)
        )
        for pos in DepartmentPosition.objects.filter(department_id=dep.id).order_by("number", "id"):
            number = pos.number
            if number in used_numbers:
                number = max(used_numbers) + 1 if used_numbers else 1
            used_numbers.add(number)
            DepartmentPosition.objects.filter(id=pos.id).update(
                department_id=canonical.id,
                number=number,
            )
        dep.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_department_departmentposition_and_more"),
    ]

    operations = [
        migrations.RunPython(merge_departments_by_name, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="department",
            name="uniq_department_office_name",
        ),
        migrations.AlterField(
            model_name="department",
            name="name",
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.RemoveField(
            model_name="department",
            name="office",
        ),
        migrations.RemoveField(
            model_name="department",
            name="color",
        ),
        migrations.AlterModelOptions(
            name="department",
            options={"ordering": ["name"]},
        ),
        migrations.AlterModelOptions(
            name="departmentposition",
            options={"ordering": ["department__name", "number"]},
        ),
    ]
