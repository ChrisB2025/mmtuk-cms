"""Add accordion_text and education_order fields to Article.

Populates existing Core Insights and "But what about...?" articles
so the education page can be driven by DB queries.
"""

from django.db import migrations, models


# Accordion data extracted from education.json before it was cleaned up.
# Format: (category, slug, accordion_text, education_order)
ACCORDION_DATA = [
    # Core Insights (6 items)
    (
        'Core Insights', 'self-financing-state',
        "A country like the UK, which has its own currency, never has to worry about running out of money. The government always creates new money when it spends, and that\u2019s how it pays for everything, not from taxes or by borrowing.",
        1,
    ),
    (
        'Core Insights', 'uk-national-debt',
        "UK debt represents money the government invested in our economy but hasn\u2019t taxed back. It corresponds exactly to the net financial savings held by the private sector; effectively, the government\u2019s liability is our asset.",
        2,
    ),
    (
        'Core Insights', 'role-of-taxation',
        "The purpose of taxes is not to fund government spending; it is to create demand for the currency and to help manage the economy.",
        3,
    ),
    (
        'Core Insights', 'understanding-inflation',
        'Inflation is defined as a sustained rise in the general price level. In the UK, inflation is not primarily caused by government spending creating "too much money" but by supply constraints, energy costs, and market power limiting how much the economy can actually produce.',
        4,
    ),
    (
        'Core Insights', 'government-vs-bond-market',
        "The UK government cannot be forced into bankruptcy by rising bond yields because it creates the money required to pay bondholders.",
        5,
    ),
    (
        'Core Insights', 'how-money-works',
        "Once you understand that money is created by the state and that taxes create demand for it, the rest of how the economy works follows as a matter of pure logic.",
        6,
    ),
    # But what about...? (10 items)
    (
        'But what about...?', 'national-debt-unsustainable',
        "No, any nation that issues its own currency and has a floating exchange rate can always pay any bill presented in its own currency. This insight lies at the heart of MMT thinking. It is based on a precise understanding of what the UK national debt is \u2013 and what it isn\u2019t.",
        1,
    ),
    (
        'But what about...?', 'wont-this-cause-inflation',
        "Inflation is caused by spending beyond the economy\u2019s productive capacity, not by government spending itself. MMT provides a framework for understanding when spending becomes inflationary and how to prevent it.",
        2,
    ),
    (
        'But what about...?', 'household-budget',
        "A currency-issuing government is fundamentally different from a household. Households must earn or borrow currency before they can spend. The UK government creates the currency that households and businesses use.",
        3,
    ),
    (
        'But what about...?', 'markets-will-punish-us',
        "Bond markets do not control currency-issuing governments in the way commonly portrayed. The UK government can always meet its obligations in sterling. Market reactions reflect expectations about future policy, not genuine solvency concerns.",
        4,
    ),
    (
        'But what about...?', 'destroy-the-currency',
        "Exchange rates are influenced by many factors including trade balances, interest rate differentials, and investor sentiment. Government spending on productive capacity can strengthen rather than weaken a currency\u2019s long-term value.",
        5,
    ),
    (
        'But what about...?', 'zimbabwe-venezuela-weimar',
        "These cases involved political collapse, war, destruction of productive capacity, or loss of monetary sovereignty. They are not examples of normal fiscal policy causing hyperinflation.",
        6,
    ),
    (
        'But what about...?', 'communism-socialism',
        "MMT is a description of how monetary systems actually operate, not a political ideology. It is compatible with a range of policy positions. Understanding the system accurately does not dictate what policies you should support.",
        7,
    ),
    (
        'But what about...?', 'no-serious-economist',
        "MMT builds on established traditions in monetary economics including Keynes, Minsky, Lerner, and institutional analysis of central banking. Its description of monetary operations aligns with how central bankers describe their own systems.",
        8,
    ),
    (
        'But what about...?', 'never-been-tried',
        "MMT describes how monetary systems already operate. Governments have always spent by creating money. The question is whether policy is designed with accurate understanding of this reality.",
        9,
    ),
    (
        'But what about...?', 'interest-rates-debt-servicing',
        "A currency-issuing government can always meet interest payments in its own currency. Interest rates are a policy choice, not a market constraint. Higher debt does not automatically mean higher interest costs.",
        10,
    ),
]


def populate_accordion_data(apps, schema_editor):
    Article = apps.get_model('content', 'Article')
    for category, slug, text, order in ACCORDION_DATA:
        Article.objects.filter(slug=slug, category=category).update(
            accordion_text=text,
            education_order=order,
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0003_reorganise_image_paths'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='accordion_text',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='article',
            name='education_order',
            field=models.PositiveIntegerField(default=9999),
        ),
        migrations.RunPython(populate_accordion_data, noop),
    ]
