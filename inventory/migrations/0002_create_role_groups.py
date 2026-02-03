from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ("admin", "employee", "company"):
        Group.objects.get_or_create(name=name)


def reverse_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["admin", "employee", "company"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_groups, reverse_groups),
    ]
