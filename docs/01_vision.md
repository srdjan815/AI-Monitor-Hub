# AI-Cenovnici Vision Document

## Purpose of AI-Cenovnici

AI-Cenovnici is a comprehensive pricing management platform designed to streamline and automate the complex process of product pricing across multiple suppliers, manufacturers, and categories. The system centralizes supplier price lists, manages product information, and provides intelligent tools for pricing optimization while maintaining full traceability of data sources. It addresses the challenges faced by businesses that need to efficiently manage large volumes of supplier data, maintain competitive pricing strategies, and ensure accurate product specifications and descriptions.

## Main Users

The primary users of AI-Cenovnici include:

- **Purchasing Managers**: Responsible for sourcing products from multiple suppliers and maintaining competitive pricing
- **Product Catalog Managers**: Oversee product information, descriptions, and technical specifications
- **Pricing Analysts**: Analyze market trends, competitor pricing, and optimize margins
- **Administrative Staff**: Handle data entry, supplier management, and system configuration
- **Business Decision Makers**: Use insights from the platform to make strategic pricing decisions

## Core Modules

The system is built around several core modules that work together seamlessly:

1. **Supplier Management Module** - Handles supplier information, contact details, and relationship management
2. **Product Catalog Module** - Manages product data including descriptions, technical specifications, and categorization
3. **Price Import Engine** - Processes and imports supplier price lists with validation and conflict resolution
4. **Pricing Rules Engine** - Applies configurable pricing rules, margins, and calculation methods
5. **AI Prompt Templates Engine** - Generates descriptions, specifications, translations, and classifications using AI
6. **Admin Interface** - Browser-based management system for manual editing and data review
7. **Audit Trail & Version History** - Tracks changes to all data with full history and attribution

## Key Business Goals

- **Efficiency**: Automate repetitive tasks like price imports and product descriptions while maintaining human oversight
- **Accuracy**: Reduce errors in pricing and product information through validation and traceability
- **Competitive Advantage**: Enable dynamic pricing strategies based on real-time market data
- **Data Integrity**: Maintain complete audit trails and version histories for all critical business data
- **Scalability**: Support growing numbers of suppliers, products, and categories without performance degradation
- **Decision Support**: Provide insights and analytics to inform pricing and procurement decisions

## Technology Stack

AI-Cenovnici is built on a modern, robust technology stack designed for reliability and maintainability:

- **Database**: PostgreSQL - chosen for its advanced features including JSONB support, ACID compliance, and excellent performance with complex queries
- **Backend Framework**: FastAPI - provides high-performance API development with automatic documentation and type safety
- **Frontend**: Browser-based admin interface using modern web technologies (HTML5, CSS3, JavaScript/TypeScript)
- **Containerization**: Docker - ensures consistent deployment environments across all stages of development and production
- **Deployment**: Designed for cross-platform compatibility between Windows development and Ubuntu production environments

## Portability from Windows Development to Ubuntu Production

The system is designed with portability as a core principle. Using Docker containers, the entire application can be developed on Windows machines using standard Windows tools and then seamlessly deployed to Ubuntu-based production servers. This approach ensures:

- Consistent environment across development, testing, and production
- Elimination of "works on my machine" issues
- Easy deployment to various cloud providers and server environments
- Standardized development workflows regardless of operating system
- Simplified scaling and maintenance operations

## Principle: Configurability from Browser

All major business rules, fields, margins, and AI prompt templates must be fully configurable through the browser-based admin interface. This principle ensures:

- No code changes required for business rule modifications
- Rapid adaptation to changing market conditions
- Self-service capability for business users
- Reduced dependency on technical staff for routine configuration changes
- Consistent user experience across all system components

## Principle: Traceability of Imported Data

All imported supplier data must remain traceable to its original source. This principle ensures:

- Complete audit trail of where information came from
- Ability to identify and resolve data discrepancies
- Compliance with business requirements for data provenance
- Historical context for pricing decisions
- Easy re-importation or replacement of specific supplier data sets

This traceability is maintained through:
- Source file tracking (name, date, supplier)
- Import session logging
- Version control of imported records
- Clear data lineage for all product information