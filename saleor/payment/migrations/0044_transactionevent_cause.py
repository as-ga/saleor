# Generated by Django 3.2.16 on 2022-11-17 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payment", "0043_auto_20220922_1146"),
    ]

    operations = [
        migrations.AddField(
            model_name="transactionevent",
            name="cause",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
    ]