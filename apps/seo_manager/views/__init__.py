from .client_views import (
    dashboard,
    client_list,
    add_client,
    client_detail,
    edit_client,
    delete_client,
    update_client_profile
)

from .keyword_views import (
    KeywordListView,
    KeywordCreateView,
    KeywordUpdateView,
    keyword_import,
    debug_keyword_data
)

from .project_views import (
    ProjectListView,
    ProjectCreateView,
    ProjectDetailView,
    edit_project,
    delete_project
)

from .analytics_views import (
    add_ga_credentials_oauth,
    add_ga_credentials_service_account,
    remove_ga_credentials,
    client_ads,
    client_dataforseo,
    google_oauth_callback  # Added this line
)

from .search_console_views import (
    client_search_console,
    add_sc_credentials,
    remove_sc_credentials
)

from .business_objective_views import (
    add_business_objective,
    edit_business_objective,
    delete_business_objective
)

from .ranking_views import (
    ranking_import,
    collect_rankings,
    backfill_rankings,
    ranking_data_management,
    export_rankings_csv
)

from .report_views import (
    generate_report
)

from .activity_views import (
    activity_log
)

from .meta_tags_views import (
    create_meta_tags_snapshot,
    create_meta_tags_snapshot_url
)
