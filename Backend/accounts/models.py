from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    city = models.CharField(max_length=100, blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    is_delivery_agent = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({'Agent' if self.is_delivery_agent else 'User'})"

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    instance.profile.save()