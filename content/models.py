from django.db import models


STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('published', 'Published'),
]


class Article(models.Model):
    CATEGORY_CHOICES = [
        ('Article', 'Article'),
        ('Commentary', 'Commentary'),
        ('Research', 'Research'),
        ('Core Ideas', 'Core Ideas'),
        ('Core Insights', 'Core Insights'),
        ('But what about...?', 'But what about...?'),
    ]
    LAYOUT_CHOICES = [
        ('default', 'Default'),
        ('simplified', 'Simplified'),
        ('rebuttal', 'Rebuttal'),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='default')
    sector = models.CharField(max_length=100, default='Economics')
    author = models.CharField(max_length=200)
    author_title = models.CharField(max_length=300, blank=True, default='')
    pub_date = models.DateField()
    read_time = models.PositiveIntegerField(default=5)
    summary = models.TextField(blank=True, default='')
    thumbnail = models.CharField(max_length=500, blank=True, default='')
    main_image = models.CharField(max_length=500, blank=True, default='')
    featured = models.BooleanField(default=False)
    color = models.CharField(max_length=20, blank=True, default='')
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pub_date']

    def __str__(self):
        return self.title


class Briefing(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    author = models.CharField(max_length=200)
    author_title = models.CharField(max_length=300, blank=True, default='')
    pub_date = models.DateField()
    read_time = models.PositiveIntegerField(default=5)
    summary = models.TextField(blank=True, default='')
    thumbnail = models.CharField(max_length=500, blank=True, default='')
    main_image = models.CharField(max_length=500, blank=True, default='')
    featured = models.BooleanField(default=False)
    draft = models.BooleanField(default=False)
    source_url = models.URLField(max_length=500, blank=True, default='')
    source_title = models.CharField(max_length=300, blank=True, default='')
    source_author = models.CharField(max_length=200, blank=True, default='')
    source_publication = models.CharField(max_length=200, blank=True, default='')
    source_date = models.DateField(null=True, blank=True)
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-pub_date']

    def __str__(self):
        return self.title


class News(models.Model):
    CATEGORY_CHOICES = [
        ('Announcement', 'Announcement'),
        ('Event', 'Event'),
        ('Press Release', 'Press Release'),
        ('Update', 'Update'),
    ]

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    date = models.DateField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    summary = models.TextField(blank=True, default='')
    thumbnail = models.CharField(max_length=500, blank=True, default='')
    main_image = models.CharField(max_length=500, blank=True, default='')
    header_video = models.URLField(max_length=500, blank=True, default='')
    registration_link = models.URLField(max_length=500, blank=True, default='')
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'news'

    def __str__(self):
        return self.title


class Bio(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=300, unique=True)
    role = models.CharField(max_length=300)
    photo = models.CharField(max_length=500, blank=True, default='')
    linkedin = models.URLField(max_length=500, blank=True, default='')
    twitter = models.URLField(max_length=500, blank=True, default='')
    website = models.URLField(max_length=500, blank=True, default='')
    advisory_board = models.BooleanField(default=False)
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class EcosystemEntry(models.Model):
    ACTIVITY_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Archived', 'Archived'),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=300, unique=True)
    country = models.CharField(max_length=100, default='UK')
    types = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True, default='')
    logo = models.CharField(max_length=500, blank=True, default='')
    website = models.URLField(max_length=500, blank=True, default='')
    twitter = models.URLField(max_length=500, blank=True, default='')
    facebook = models.URLField(max_length=500, blank=True, default='')
    youtube = models.URLField(max_length=500, blank=True, default='')
    discord = models.URLField(max_length=500, blank=True, default='')
    activity_status = models.CharField(max_length=10, choices=ACTIVITY_STATUS_CHOICES, default='Active')
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'ecosystem entries'

    def __str__(self):
        return self.name


class LocalGroup(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=300, unique=True)
    title = models.CharField(max_length=300)
    tagline = models.CharField(max_length=500)
    header_image = models.CharField(max_length=500, blank=True, default='')
    leader_name = models.CharField(max_length=200, blank=True, default='')
    leader_intro = models.TextField(blank=True, default='')
    discord_link = models.URLField(max_length=500, blank=True, default='')
    active = models.BooleanField(default=True)
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class LocalEvent(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    local_group = models.ForeignKey(
        LocalGroup, on_delete=models.PROTECT, related_name='events',
        null=True, blank=True,
    )
    date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    tag = models.CharField(max_length=100)
    location = models.CharField(max_length=500)
    description = models.TextField()
    link = models.URLField(max_length=500, blank=True, default='')
    image = models.CharField(max_length=500, blank=True, default='')
    partner_event = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return self.title


class LocalNews(models.Model):
    heading = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    text = models.TextField()
    local_group = models.ForeignKey(
        LocalGroup, on_delete=models.PROTECT, related_name='news',
        null=True, blank=True,
    )
    date = models.DateField()
    link = models.URLField(max_length=500, blank=True, default='')
    image = models.CharField(max_length=500, blank=True, default='')
    body = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'local news'

    def __str__(self):
        return self.heading
