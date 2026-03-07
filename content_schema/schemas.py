"""
Page type definitions for the MMTUK CMS page editor.

Content type schemas have been replaced by Django models (content/models.py).
Only PAGE_TYPES and access-control constants remain.
"""

PAGE_TYPES = {
    "home": {
        "name": "Home",
        "route": "/",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "slides": {
                        "type": "object_array",
                        "label": "Hero Slides",
                        "item_fields": {
                            "tag": {"type": "string", "label": "Tag (e.g. Policy research)"},
                            "text": {"type": "string", "label": "Slide text / blurb"},
                            "link_href": {"type": "string", "label": "Link URL"},
                            "link_label": {"type": "string", "label": "Link label (visible text)"},
                        },
                    },
                },
            },
            "research_section": {
                "name": "Research Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                },
            },
            "education_section": {
                "name": "Education Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                },
            },
            "community_section": {
                "name": "Community Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_1_href": {"type": "string", "label": "Card 1 Link"},
                    "card_1_button_label": {"type": "string", "label": "Card 1 Button Label"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_2_href": {"type": "string", "label": "Card 2 Link"},
                    "card_2_button_label": {"type": "string", "label": "Card 2 Button Label"},
                    "card_3_heading": {"type": "string", "label": "Card 3 Heading"},
                    "card_3_body": {"type": "string", "label": "Card 3 Body"},
                    "card_3_href": {"type": "string", "label": "Card 3 Link"},
                    "card_3_button_label": {"type": "string", "label": "Card 3 Button Label"},
                },
            },
            "testimonials": {
                "name": "Testimonials",
                "fields": {
                    "items": {
                        "type": "object_array",
                        "label": "Testimonial Items",
                        "item_fields": {
                            "quote": {"type": "string", "label": "Quote"},
                            "name": {"type": "string", "label": "Name"},
                            "title": {"type": "string", "label": "Title / Role"},
                        },
                    },
                },
            },
            "contact": {
                "name": "Contact",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
        },
        "admin_only": False,
    },
    "research": {
        "name": "Research",
        "route": "/research",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "policy_areas": {
                "name": "Policy Areas",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "job_guarantee": {
                "name": "Job Guarantee",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "feature_1": {"type": "string", "label": "Feature 1"},
                    "feature_2": {"type": "string", "label": "Feature 2"},
                    "feature_3": {"type": "string", "label": "Feature 3"},
                    "button_label": {"type": "string", "label": "Button Label"},
                    "button_href": {"type": "string", "label": "Button Link"},
                },
            },
            "zirp": {
                "name": "ZIRP",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "feature_1": {"type": "string", "label": "Feature 1"},
                    "feature_2": {"type": "string", "label": "Feature 2"},
                    "feature_3": {"type": "string", "label": "Feature 3"},
                    "wip_notice": {"type": "string", "label": "Work in Progress Notice"},
                },
            },
            "briefings": {
                "name": "MMT Briefings",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "tag_label": {"type": "string", "label": "Tag Label"},
                    "read_button_label": {"type": "string", "label": "Read Button Label"},
                    "view_all_label": {"type": "string", "label": "View All Label"},
                },
            },
            "approach": {
                "name": "Our Approach",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "card_1_heading": {"type": "string", "label": "Card 1 Heading"},
                    "card_1_body": {"type": "string", "label": "Card 1 Body"},
                    "card_2_heading": {"type": "string", "label": "Card 2 Heading"},
                    "card_2_body": {"type": "string", "label": "Card 2 Body"},
                    "card_3_heading": {"type": "string", "label": "Card 3 Heading"},
                    "card_3_body": {"type": "string", "label": "Card 3 Body"},
                    "card_4_heading": {"type": "string", "label": "Card 4 Heading"},
                    "card_4_body": {"type": "string", "label": "Card 4 Body"},
                    "card_5_heading": {"type": "string", "label": "Card 5 Heading"},
                    "card_5_body": {"type": "string", "label": "Card 5 Body"},
                },
            },
        },
        "admin_only": False,
    },
    "job-guarantee": {
        "name": "Job Guarantee",
        "route": "/job-guarantee",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "header": {
                "name": "Header",
                "fields": {
                    "page_title": {"type": "string", "label": "Page Title (H1)"},
                    "policy_type": {"type": "string", "label": "Policy Type Label"},
                },
            },
            "metadata": {
                "name": "Publication Metadata",
                "fields": {
                    "publication_date": {"type": "string", "label": "Publication Date"},
                    "download_url": {"type": "string", "label": "PDF Download URL"},
                    "video_url": {"type": "string", "label": "Vimeo Video URL"},
                },
            },
            "body": {
                "name": "Body Content",
                "fields": {
                    "content": {"type": "markdown", "label": "Body Content"},
                },
            },
        },
        "admin_only": False,
    },
    "education": {
        "name": "Education",
        "route": "/education",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "library": {
                "name": "MMTUK Library",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                    "coming_soon_label": {"type": "string", "label": "Coming Soon Label"},
                },
            },
            "what_is_mmt": {
                "name": "What is MMT?",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "paragraph_1": {"type": "string", "label": "Paragraph 1"},
                    "paragraph_2": {"type": "string", "label": "Paragraph 2"},
                },
            },
            "core_insights": {
                "name": "MMT Core Insights",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "items": {
                        "type": "object_array",
                        "label": "Accordion Items",
                        "item_fields": {
                            "title": {"type": "string", "label": "Title"},
                            "body": {"type": "string", "label": "Body"},
                            "link_href": {"type": "string", "label": "Read More Link"},
                        },
                    },
                },
            },
            "objections": {
                "name": "But what about...?",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "items": {
                        "type": "object_array",
                        "label": "Objection Items",
                        "item_fields": {
                            "title": {"type": "string", "label": "Title"},
                            "body": {"type": "string", "label": "Body"},
                            "link_href": {"type": "string", "label": "Read More Link"},
                        },
                    },
                },
            },
            "advisory_services": {
                "name": "Advisory Services",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "paragraph_1": {"type": "string", "label": "Paragraph 1"},
                },
            },
        },
        "admin_only": False,
    },
    "community": {
        "name": "Community",
        "route": "/community",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "local_groups": {
                "name": "Local Groups",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "events": {
                "name": "Upcoming Events",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "discord": {
                "name": "Discord CTA",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
        },
        "admin_only": False,
    },
    "about-us": {
        "name": "About Us",
        "route": "/about-us",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "news": {
                "name": "MMTUK News",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Read More Button Label"},
                },
            },
            "events": {
                "name": "MMTUK Events",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "button_label": {"type": "string", "label": "Learn More Button Label"},
                },
            },
            "steering_group": {
                "name": "Steering Group",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "order": {"type": "string_array", "label": "Display Order (one name per line)"},
                },
            },
            "advisory_board": {
                "name": "Advisory Board",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
        },
        "admin_only": False,
    },
    "donate": {
        "name": "Donate",
        "route": "/donate",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "founder_section": {
                "name": "Founder Member Scheme",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "body": {"type": "string", "label": "Body"},
                },
            },
            "founder_cta": {
                "name": "Founder CTA Card",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "plan_label": {"type": "string", "label": "Plan Label"},
                    "plan_amount": {"type": "string", "label": "Plan Amount"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "research_donations": {
                "name": "Research Donations",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                    "bullet_1": {"type": "string", "label": "Bullet 1"},
                    "bullet_2": {"type": "string", "label": "Bullet 2"},
                    "bullet_3": {"type": "string", "label": "Bullet 3"},
                },
            },
            "pricing": {
                "name": "Pricing Tiers",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                    "supporter_label": {"type": "string", "label": "Supporter Label"},
                    "supporter_amount": {"type": "string", "label": "Supporter Amount"},
                    "supporter_period": {"type": "string", "label": "Supporter Period"},
                    "supporter_button": {"type": "string", "label": "Supporter Button"},
                    "founder_label": {"type": "string", "label": "Founder Label"},
                    "founder_amount": {"type": "string", "label": "Founder Amount"},
                    "founder_period": {"type": "string", "label": "Founder Period"},
                    "founder_button": {"type": "string", "label": "Founder Button"},
                    "patron_label": {"type": "string", "label": "Patron Label"},
                    "patron_amount": {"type": "string", "label": "Patron Amount"},
                    "patron_period": {"type": "string", "label": "Patron Period"},
                    "patron_button": {"type": "string", "label": "Patron Button"},
                },
            },
            "thank_you": {
                "name": "Thank You",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "body": {"type": "string", "label": "Body"},
                },
            },
        },
        "admin_only": False,
    },
    "founders": {
        "name": "Founders",
        "route": "/founders",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "subtitle": {"type": "string", "label": "Subtitle"},
                },
            },
            "feature_1": {
                "name": "Feature 1",
                "fields": {
                    "tag": {"type": "string", "label": "Tag"},
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                },
            },
            "feature_2": {
                "name": "Feature 2 (Countdown)",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tag": {"type": "string", "label": "Tag"},
                    "date": {"type": "string", "label": "Deadline Date Label"},
                    "countdown_target": {"type": "string", "label": "Countdown Target (MM/DD/YYYY HH:mm:ss)"},
                    "tier_label": {"type": "string", "label": "Tier Label"},
                    "tier_description": {"type": "string", "label": "Tier Description"},
                    "tier_price": {"type": "string", "label": "Tier Price"},
                    "button_label": {"type": "string", "label": "Button Label"},
                    "form_success_message": {"type": "string", "label": "Form Success Message"},
                    "form_error_message": {"type": "string", "label": "Form Error Message"},
                },
            },
            "cta_section": {
                "name": "CTA Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "description": {"type": "string", "label": "Description"},
                    "trust_label": {"type": "string", "label": "Trust Label"},
                    "tier_label": {"type": "string", "label": "Tier Label"},
                    "tier_description": {"type": "string", "label": "Tier Description"},
                    "tier_price": {"type": "string", "label": "Tier Price"},
                    "button_label": {"type": "string", "label": "Button Label"},
                },
            },
            "testimonials": {
                "name": "Testimonials",
                "fields": {
                    "items": {
                        "type": "object_array",
                        "label": "Testimonial Items",
                        "item_fields": {
                            "quote": {"type": "string", "label": "Quote"},
                            "name": {"type": "string", "label": "Name"},
                            "role": {"type": "string", "label": "Role"},
                        },
                    },
                },
            },
            "faq": {
                "name": "FAQs",
                "fields": {
                    "heading": {"type": "string", "label": "Section Heading"},
                    "intro": {"type": "string", "label": "Intro Text"},
                    "items": {
                        "type": "object_array",
                        "label": "FAQ Items",
                        "item_fields": {
                            "question": {"type": "string", "label": "Question"},
                            "answer": {"type": "string", "label": "Answer"},
                        },
                    },
                    "contact_heading": {"type": "string", "label": "Contact Heading"},
                    "contact_intro": {"type": "string", "label": "Contact Intro"},
                },
            },
        },
        "admin_only": False,
    },
    "join": {
        "name": "Join",
        "route": "/join",
        "sections": {
            "meta": {
                "name": "Meta",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "description": {"type": "string", "label": "Meta Description"},
                },
            },
            "hero": {
                "name": "Hero",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "tagline": {"type": "string", "label": "Tagline"},
                },
            },
            "join_section": {
                "name": "Join Section",
                "fields": {
                    "heading": {"type": "string", "label": "Heading"},
                    "subtitle": {"type": "string", "label": "Subtitle"},
                    "intro": {"type": "string", "label": "Intro Paragraph"},
                    "benefits": {"type": "string_array", "label": "Benefits List (one per line)"},
                },
            },
        },
        "admin_only": False,
    },
    "site-config": {
        "name": "Site Config",
        "route": "(global)",
        "editor_url_name": "site_config_editor",
        "sections": {
            "settings": {
                "name": "Site Settings",
                "fields": {
                    "discord_url": {"type": "string", "label": "Discord Invite URL", "admin_only": True},
                    "stripe_links.supporter": {"type": "string", "label": "Stripe Link \u2014 Supporter (monthly)", "admin_only": True},
                    "stripe_links.founder": {"type": "string", "label": "Stripe Link \u2014 Founder (one-off)", "admin_only": True},
                    "stripe_links.patron": {"type": "string", "label": "Stripe Link \u2014 Patron (variable)", "admin_only": True},
                    "action_network_form_id": {"type": "string", "label": "Action Network Form ID", "admin_only": True},
                    "founder_scheme.current_count": {"type": "number", "label": "Founder Scheme \u2014 Current Count"},
                    "founder_scheme.target_count": {"type": "number", "label": "Founder Scheme \u2014 Target Count"},
                    "founder_scheme.deadline_iso": {"type": "string", "label": "Countdown Deadline (MM/DD/YYYY HH:mm:ss)"},
                    "founder_scheme.deadline_display": {"type": "string", "label": "Display Deadline (e.g. Sun 17 May 2026)"},
                    "founder_scheme.milestone_message": {"type": "string", "label": "Milestone Message"},
                    "announcement_bar.enabled": {"type": "boolean", "label": "Announcement Bar \u2014 Enabled"},
                    "announcement_bar.message": {"type": "string", "label": "Announcement Bar \u2014 Message"},
                    "announcement_bar.link": {"type": "string", "label": "Announcement Bar \u2014 Link URL"},
                },
            }
        },
        "admin_only": True,
    },
    "privacy-policy": {
        "name": "Privacy Policy",
        "route": "/privacy-policy",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "body": {"type": "markdown", "label": "Body Content"},
                },
            }
        },
        "admin_only": False,
    },
    "terms-of-engagement": {
        "name": "Terms of Engagement",
        "route": "/terms-of-engagement",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "body": {"type": "markdown", "label": "Body Content"},
                },
            }
        },
        "admin_only": False,
    },
    "cookie-preferences": {
        "name": "Cookie Preferences",
        "route": "/cookie-preferences",
        "sections": {
            "content": {
                "name": "Page Content",
                "fields": {
                    "title": {"type": "string", "label": "Page Title"},
                    "last_updated": {"type": "string", "label": "Last Updated"},
                    "intro": {"type": "markdown", "label": "Introduction (How we use cookies + Cookie categories)"},
                    "services_list": {"type": "markdown", "label": "Cookies and Services"},
                },
            }
        },
        "admin_only": False,
    },
}

# Roles permitted to edit any page
PAGE_EDITOR_ROLES = {"admin", "editor"}

# Pages where only admin can access at all
ADMIN_ONLY_PAGES = {"site-config"}

# Field-level admin restrictions per page
ADMIN_ONLY_FIELDS = {
    "site-config": {
        "discord_url",
        "stripe_links.supporter",
        "stripe_links.founder",
        "stripe_links.patron",
        "action_network_form_id",
    },
}
