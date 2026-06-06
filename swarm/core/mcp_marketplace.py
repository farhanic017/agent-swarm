from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MCPMarketplaceEntry:
    name: str
    category: str
    capabilities: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "capabilities": list(self.capabilities),
        }


MCP_MARKETPLACE: tuple[MCPMarketplaceEntry, ...] = (
    MCPMarketplaceEntry("Supabase", "Dev & Infrastructure", ("database", "auth", "storage", "backend")),
    MCPMarketplaceEntry("Cloudflare Developer Platform", "Dev & Infrastructure", ("workers", "kv", "compute")),
    MCPMarketplaceEntry("Datadog", "Dev & Infrastructure", ("logs", "metrics", "monitors")),
    MCPMarketplaceEntry("PagerDuty", "Dev & Infrastructure", ("incidents", "on_call")),
    MCPMarketplaceEntry("incident.io", "Dev & Infrastructure", ("incident_management",)),
    MCPMarketplaceEntry("Honeycomb", "Dev & Infrastructure", ("observability", "slos")),
    MCPMarketplaceEntry("Monte Carlo", "Dev & Infrastructure", ("data_observability", "ai_observability")),
    MCPMarketplaceEntry("Google Compute Engine", "Dev & Infrastructure", ("vm_management",)),
    MCPMarketplaceEntry("Google Cloud BigQuery", "Dev & Infrastructure", ("sql_analytics",)),
    MCPMarketplaceEntry("QuickNode", "Dev & Infrastructure", ("blockchain_infrastructure",)),
    MCPMarketplaceEntry("Notion", "Productivity & Project Management", ("docs", "databases", "pages")),
    MCPMarketplaceEntry("Asana", "Productivity & Project Management", ("tasks", "projects", "goals")),
    MCPMarketplaceEntry("ClickUp", "Productivity & Project Management", ("project_management",)),
    MCPMarketplaceEntry("Todoist", "Productivity & Project Management", ("task_management",)),
    MCPMarketplaceEntry("Atlassian Rovo", "Productivity & Project Management", ("jira", "confluence")),
    MCPMarketplaceEntry("Microsoft 365", "Productivity & Project Management", ("sharepoint", "outlook", "teams", "onedrive")),
    MCPMarketplaceEntry("Whimsical", "Productivity & Project Management", ("flowcharts", "mindmaps", "wireframes")),
    MCPMarketplaceEntry("Miro", "Productivity & Project Management", ("visual_boards",)),
    MCPMarketplaceEntry("Glean", "Productivity & Project Management", ("enterprise_search", "knowledge")),
    MCPMarketplaceEntry("Gmail", "Productivity & Project Management", ("email", "search", "drafts")),
    MCPMarketplaceEntry("Google Calendar", "Productivity & Project Management", ("calendar", "scheduling")),
    MCPMarketplaceEntry("Google Drive", "Productivity & Project Management", ("files", "docs", "search")),
    MCPMarketplaceEntry("Slack", "Communication & Messaging", ("messages", "channels", "canvases")),
    MCPMarketplaceEntry("Twilio", "Communication & Messaging", ("sms", "communications")),
    MCPMarketplaceEntry("IFTTT", "Communication & Messaging", ("automation", "integrations")),
    MCPMarketplaceEntry("Intercom", "Communication & Messaging", ("customer_conversations",)),
    MCPMarketplaceEntry("Adobe for creativity", "Design & Creative", ("firefly", "express", "creative_tools")),
    MCPMarketplaceEntry("Adobe Marketing Agent", "Design & Creative", ("campaign_insights",)),
    MCPMarketplaceEntry("Adobe Customer Journey Analytics", "Design & Creative", ("reporting", "journey_analytics")),
    MCPMarketplaceEntry("Cloudinary", "Design & Creative", ("image_management", "video_management")),
    MCPMarketplaceEntry("Magic Patterns", "Design & Creative", ("ui_design_iteration",)),
    MCPMarketplaceEntry("Descript", "Design & Creative", ("video_import", "video_editing")),
    MCPMarketplaceEntry("Goodnotes", "Design & Creative", ("svg", "diagrams", "markdown_docs")),
    MCPMarketplaceEntry("Webflow", "Design & Creative", ("cms", "pages", "assets")),
    MCPMarketplaceEntry("Figma", "Design & Creative", ("design", "prototype", "handoff")),
    MCPMarketplaceEntry("Canva", "Design & Creative", ("templates", "brand_assets")),
    MCPMarketplaceEntry("Hugging Face", "Research & Science", ("models", "datasets", "spaces")),
    MCPMarketplaceEntry("HubSpot", "CRM & Sales", ("crm", "insights")),
    MCPMarketplaceEntry("Zoho CRM", "CRM & Sales", ("crm_workflows",)),
    MCPMarketplaceEntry("Salesforce via Outreach", "CRM & Sales", ("sales_engagement",)),
    MCPMarketplaceEntry("Salesloft", "CRM & Sales", ("deals", "pipeline", "engagement")),
    MCPMarketplaceEntry("Close", "CRM & Sales", ("crm_tools",)),
    MCPMarketplaceEntry("Attio", "CRM & Sales", ("contacts", "records", "tasks")),
    MCPMarketplaceEntry("Day AI", "CRM & Sales", ("prospects", "customers")),
    MCPMarketplaceEntry("Sybill", "CRM & Sales", ("sales_calls", "deals", "pipeline")),
    MCPMarketplaceEntry("Outreach", "CRM & Sales", ("sequences", "prospects", "accounts")),
    MCPMarketplaceEntry("Quo", "CRM & Sales", ("call_insights", "messaging")),
    MCPMarketplaceEntry("Stripe", "Finance & Payments", ("payments", "customers", "products")),
    MCPMarketplaceEntry("Razorpay", "Finance & Payments", ("payments_dashboard",)),
    MCPMarketplaceEntry("Intuit QuickBooks", "Finance & Payments", ("profit_loss", "cash_flow")),
    MCPMarketplaceEntry("Zoho Books", "Finance & Payments", ("invoices", "expenses", "accounting")),
    MCPMarketplaceEntry("Brex", "Finance & Payments", ("cards", "expenses")),
    MCPMarketplaceEntry("Carta", "Finance & Payments", ("private_capital",)),
    MCPMarketplaceEntry("FMP", "Finance & Payments", ("market_data",)),
    MCPMarketplaceEntry("Interactive Brokers", "Finance & Payments", ("trading", "portfolio")),
    MCPMarketplaceEntry("Morningstar Credit Analytics", "Finance & Payments", ("credit_intelligence",)),
    MCPMarketplaceEntry("LSEG", "Finance & Payments", ("fx", "bonds", "options", "rates")),
    MCPMarketplaceEntry("D&B Risk Analytics", "Finance & Payments", ("commercial_risk",)),
    MCPMarketplaceEntry("Pigment", "Finance & Payments", ("business_data_analysis",)),
    MCPMarketplaceEntry("Quartr", "Finance & Payments", ("company_research", "financials")),
    MCPMarketplaceEntry("CB Insights", "Finance & Payments", ("private_company_intelligence",)),
    MCPMarketplaceEntry("LunarCrush", "Finance & Payments", ("crypto_social_data",)),
    MCPMarketplaceEntry("Crypto.com", "Finance & Payments", ("crypto_prices",)),
    MCPMarketplaceEntry("CoinDesk", "Finance & Payments", ("crypto_data", "indices")),
    MCPMarketplaceEntry("Blockscout", "Finance & Payments", ("on_chain_data",)),
    MCPMarketplaceEntry("Airwallex Developer", "Finance & Payments", ("global_payments", "fx")),
    MCPMarketplaceEntry("Shopify", "E-commerce", ("store", "products", "orders", "customers")),
    MCPMarketplaceEntry("Order by Cash App", "E-commerce", ("local_food_ordering",)),
    MCPMarketplaceEntry("Semrush", "Marketing & SEO", ("seo", "competitor_research")),
    MCPMarketplaceEntry("Ahrefs", "Marketing & SEO", ("backlinks", "keywords", "brand_radar")),
    MCPMarketplaceEntry("Supermetrics", "Marketing & SEO", ("marketing_data",)),
    MCPMarketplaceEntry("Polar Analytics", "Marketing & SEO", ("marketing_analytics",)),
    MCPMarketplaceEntry("Omni Analytics", "Marketing & SEO", ("natural_language_queries",)),
    MCPMarketplaceEntry("Similarweb", "Marketing & SEO", ("traffic", "market_data")),
    MCPMarketplaceEntry("Local Falcon", "Marketing & SEO", ("local_search_visibility",)),
    MCPMarketplaceEntry("Motion Creative Analytics", "Marketing & SEO", ("meta_ad_creative",)),
    MCPMarketplaceEntry("Box", "Cloud & Storage", ("content_search", "ai_qa")),
    MCPMarketplaceEntry("PandaDoc", "Cloud & Storage", ("docs", "send", "sign")),
    MCPMarketplaceEntry("DocuSeal", "Cloud & Storage", ("document_signing", "templates")),
    MCPMarketplaceEntry("NetDocuments", "Cloud & Storage", ("legal_documents",)),
    MCPMarketplaceEntry("Dremio Cloud", "Cloud & Storage", ("lakehouse_analytics",)),
    MCPMarketplaceEntry("AWS Marketplace", "Cloud & Storage", ("cloud_solutions",)),
    MCPMarketplaceEntry("Workable", "HR & Recruiting", ("hiring", "hr")),
    MCPMarketplaceEntry("Metaview", "HR & Recruiting", ("recruiting_ai",)),
    MCPMarketplaceEntry("Gusto", "HR & Recruiting", ("payroll", "employees", "compensation")),
    MCPMarketplaceEntry("Shapes", "HR & Recruiting", ("people_data", "org_insights")),
    MCPMarketplaceEntry("CoCounsel Legal", "Legal", ("legal_research",)),
    MCPMarketplaceEntry("Legal Data Hunter", "Legal", ("legal_docs", "jurisdictions")),
    MCPMarketplaceEntry("Descrybe Legal Engine", "Legal", ("us_primary_law",)),
    MCPMarketplaceEntry("LegalZoom", "Legal", ("attorney_guidance", "business_tools")),
    MCPMarketplaceEntry("Midpage Legal Research", "Legal", ("case_analysis",)),
    MCPMarketplaceEntry("CourtListener", "Legal", ("court_records",)),
    MCPMarketplaceEntry("Lawve AI", "Legal", ("expert_legal_skills",)),
    MCPMarketplaceEntry("Harvey", "Legal", ("legal_qa", "vaults", "research")),
    MCPMarketplaceEntry("PubMed", "Research & Science", ("biomedical_literature",)),
    MCPMarketplaceEntry("Consensus", "Research & Science", ("scientific_search",)),
    MCPMarketplaceEntry("Scite", "Research & Science", ("evidence_research",)),
    MCPMarketplaceEntry("protocols.io", "Research & Science", ("science_protocols",)),
    MCPMarketplaceEntry("Microsoft Learn", "Research & Science", ("microsoft_docs", "code_samples")),
    MCPMarketplaceEntry("Exa", "Research & Science", ("web_search", "code_docs")),
    MCPMarketplaceEntry("Guru", "Knowledge & Notes", ("company_knowledge",)),
    MCPMarketplaceEntry("Craft", "Knowledge & Notes", ("notes", "second_brain")),
    MCPMarketplaceEntry("Klarity", "Knowledge & Notes", ("process_explorer",)),
    MCPMarketplaceEntry("ICD-10 Codes", "Healthcare", ("diagnosis_codes", "procedure_codes")),
    MCPMarketplaceEntry("NPI Registry", "Healthcare", ("provider_lookup",)),
    MCPMarketplaceEntry("Medidata", "Healthcare", ("clinical_trials",)),
    MCPMarketplaceEntry("Alma", "Healthcare", ("nutrition", "meal_data")),
    MCPMarketplaceEntry("Expedia", "Travel & Lifestyle", ("flights", "hotels")),
    MCPMarketplaceEntry("Booking.com", "Travel & Lifestyle", ("accommodations",)),
    MCPMarketplaceEntry("Turkish Airlines", "Travel & Lifestyle", ("flights", "city_guides")),
    MCPMarketplaceEntry("lastminute.com", "Travel & Lifestyle", ("flights", "packages")),
    MCPMarketplaceEntry("AllTrails", "Travel & Lifestyle", ("trails",)),
    MCPMarketplaceEntry("Strava", "Travel & Lifestyle", ("fitness", "activity_data")),
    MCPMarketplaceEntry("Fever Event Discovery", "Travel & Lifestyle", ("events",)),
    MCPMarketplaceEntry("Taskrabbit", "Travel & Lifestyle", ("local_services",)),
    MCPMarketplaceEntry("Uber", "Travel & Lifestyle", ("ride_estimates",)),
    MCPMarketplaceEntry("Spotify", "Music & Entertainment", ("music", "podcasts")),
    MCPMarketplaceEntry("Melon", "Music & Entertainment", ("korean_music_charts",)),
    MCPMarketplaceEntry("Play Sheet Music", "Music & Entertainment", ("generate_music", "play_music")),
    MCPMarketplaceEntry("Bitly", "Other / Specialized", ("links", "qr_codes")),
    MCPMarketplaceEntry("Grain", "Other / Specialized", ("meeting_intelligence",)),
    MCPMarketplaceEntry("Customer.io", "Other / Specialized", ("customer_messaging",)),
    MCPMarketplaceEntry("Pylon", "Other / Specialized", ("b2b_support",)),
    MCPMarketplaceEntry("Unthread", "Other / Specialized", ("slack_support_tickets",)),
    MCPMarketplaceEntry("Zoho Desk", "Other / Specialized", ("customer_support",)),
    MCPMarketplaceEntry("Ticket Tailor", "Other / Specialized", ("event_ticketing",)),
    MCPMarketplaceEntry("Tines", "Other / Specialized", ("security_automation",)),
    MCPMarketplaceEntry("MT Newswires", "Other / Specialized", ("financial_news",)),
    MCPMarketplaceEntry("Kindora Funder Discovery", "Other / Specialized", ("nonprofit_funders",)),
    MCPMarketplaceEntry("Candid", "Other / Specialized", ("nonprofit_research", "funder_research")),
    MCPMarketplaceEntry("Learning Commons Knowledge Graph", "Other / Specialized", ("k12_standards",)),
    MCPMarketplaceEntry("Three.js 3D Viewer", "Other / Specialized", ("interactive_3d",)),
    MCPMarketplaceEntry("Relativity", "Other / Specialized", ("legal_data_platform",)),
    MCPMarketplaceEntry("Visier", "Other / Specialized", ("workforce_analytics",)),
    MCPMarketplaceEntry("Natoma", "Other / Specialized", ("internal_tools", "enterprise_apps")),
    MCPMarketplaceEntry("Base44", "Other / Specialized", ("no_code_apps",)),
    MCPMarketplaceEntry("Chronograph", "Other / Specialized", ("pe_vc_portfolio_data",)),
)


def list_mcp_marketplace(category: str | None = None, query: str | None = None) -> list[dict]:
    entries = MCP_MARKETPLACE
    if category:
        needle = category.lower()
        entries = tuple(entry for entry in entries if needle in entry.category.lower())
    if query:
        needle = query.lower()
        entries = tuple(
            entry for entry in entries
            if needle in entry.name.lower() or needle in " ".join(entry.capabilities).lower()
        )
    return [entry.to_dict() for entry in entries]


def plan_mcp_connectors(task: str, limit: int = 8) -> dict:
    task_lower = task.lower()
    scored = []
    for entry in MCP_MARKETPLACE:
        text = f"{entry.name} {entry.category} {' '.join(entry.capabilities)}".lower()
        score = sum(1 for token in set(task_lower.split()) if token and token in text)
        if score:
            scored.append((score, entry))
    scored.sort(key=lambda item: (item[0], item[1].name), reverse=True)
    selected = [entry.to_dict() for _, entry in scored[:limit]]
    return {
        "task": task,
        "selected": selected,
        "install_policy": "Connect only requested MCPs; do not enable broad access by default.",
        "token_policy": "Use MCP lookup for external state instead of rereading large docs or guessing.",
    }
