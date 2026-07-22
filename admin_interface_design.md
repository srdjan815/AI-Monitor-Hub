# AI-Cenovnici Admin Interface Architecture

## Overview
This document outlines the architecture for the browser-based admin interface of AI-Cenovnici, designed to support manual editing, reviewing imported data, and managing all aspects of the product catalog system.

## Admin Interface Screens

### 1. Dashboard
- System overview with key metrics
- Recent activity feed
- Quick access to main sections
- Import status monitoring
- Alert notifications

### 2. Products Management
#### Main Product List View
- Filter by category, supplier, manufacturer, status
- Search by SKU, name, EAN
- Sort by various fields
- Bulk actions (activate/deactivate, export)
- Pagination and responsive design

#### Product Detail View
- Basic information tab (SKU, name, description, EAN, weight, dimensions)
- Category assignment
- Manufacturer and supplier selection
- Specifications tab (with JSONB editor for category-specific fields)
- Price history tab (viewing version history)
- Audit log tab (changes to this product)

#### Product Creation/Editing Form
- Tabbed interface for different sections
- Real-time validation
- Auto-save functionality
- Undo/redo capabilities
- Rich text editor for descriptions

### 3. Suppliers Management
#### Supplier List View
- Filter and search capabilities
- Status indicators (active/inactive)
- Contact information overview

#### Supplier Detail View
- Basic supplier information
- Contact details
- Payment terms
- Currency settings
- Import history tracking

#### Supplier Creation/Editing Form
- Comprehensive form with all supplier fields
- Validation for required fields
- Save and preview options

### 4. Manufacturers Management
#### Manufacturer List View
- Filter by status
- Search by name
- Quick view of contact information

#### Manufacturer Detail View
- Basic manufacturer information
- Contact details
- Website and other relevant links
- Product count indicator

#### Manufacturer Creation/Editing Form
- Complete form for manufacturer data
- Validation and auto-save

### 5. Categories Management
#### Category List View
- Hierarchical view of categories (tree structure)
- Filter by status
- Search capabilities

#### Category Detail View
- Category information
- Parent category assignment
- Description and other details
- Product count indicator

#### Category Creation/Editing Form
- Form with hierarchical category selection
- Validation for required fields
- Preview of category hierarchy

### 6. Import Management
#### Import Sessions List
- Filter by supplier, status, date range
- Status indicators (pending, processing, completed, failed)
- Progress tracking
- Error details view

#### Import Session Detail
- File information
- Records processed vs failed
- Error messages and logs
- Retry functionality

#### Import Configuration
- Supplier selection
- File upload interface
- Mapping configuration for CSV/Excel fields
- Preview of data to be imported
- Validation rules configuration

### 7. Pricing Rules Management
#### Rules List View
- Filter by category, manufacturer, supplier, product
- Status indicators
- Quick search capabilities

#### Rule Detail View
- Rule parameters
- Scope (category, manufacturer, supplier, or specific product)
- Pricing calculation method

#### Rule Creation/Editing Form
- Multi-level scope selection
- Margin percentage or fixed price input
- Validation rules for inputs

### 8. AI Prompt Templates Management
#### Templates List View
- Filter by template type
- Search by name
- Status indicators

#### Template Detail View
- Full template content
- Type indicator
- Description field

#### Template Creation/Editing Form
- WYSIWYG editor for prompt text
- Type selection (description, specification, translation, classification)
- Validation and preview capabilities

### 9. Audit Log Viewer
#### Audit Log List
- Filter by date range, user, action type, table name
- Search functionality
- Pagination

#### Audit Log Detail View
- Full details of the change
- Before/after values comparison
- User information
- Timestamp and IP address

## Technical Architecture

### Frontend Framework
- React.js with TypeScript for type safety
- Material-UI or similar component library for consistent UI
- Responsive design for desktop and mobile access
- State management with Redux or Context API

### Backend Integration
- RESTful API endpoints for all admin functions
- Authentication and authorization system
- Real-time updates via WebSocket or polling
- Data validation at both frontend and backend levels

### Data Handling
#### CRUD Operations
- All main entities (products, suppliers, manufacturers, categories) support full CRUD operations
- Batch operations for efficient management of multiple records

#### Data Validation
- Client-side validation for immediate feedback
- Server-side validation for data integrity
- Constraint checking at database level

#### File Management
- Support for importing supplier price lists (CSV, Excel)
- File upload with progress indicators
- Preview and mapping capabilities before import

### Security Considerations
- Role-based access control (RBAC)
- Session management
- Input sanitization to prevent injection attacks
- Secure file handling for imports
- Audit logging of all admin activities

## User Experience Design Principles

1. **Intuitive Navigation**
   - Consistent navigation structure across all screens
   - Clear breadcrumbs for multi-level views
   - Quick access to frequently used features

2. **Responsive Design**
   - Adapts to different screen sizes
   - Mobile-friendly touch targets
   - Optimized layouts for various devices

3. **Data Visualization**
   - Dashboard with key metrics and charts
   - Progress indicators for import processes
   - Visual feedback for user actions

4. **Accessibility**
   - WCAG 2.1 compliance
   - Keyboard navigation support
   - Screen reader compatibility

5. **Performance Optimization**
   - Lazy loading of data
   - Efficient search and filtering
   - Loading states for async operations

## Implementation Approach

### Phase 1: Core Management Screens
1. Dashboard
2. Products management (list, detail, creation)
3. Suppliers management 
4. Manufacturers management
5. Categories management

### Phase 2: Advanced Features
1. Import system with file handling
2. Pricing rules management
3. AI prompt templates management
4. Audit log viewer

### Phase 3: Enhancements
1. Advanced filtering and search
2. Bulk operations
3. Reporting capabilities
4. Customization options

## Integration Points

1. **Database Layer**
   - Direct integration with PostgreSQL schema designed above
   - Support for JSONB queries in product specifications

2. **API Layer**
   - FastAPI backend endpoints for all admin functions
   - Authentication and authorization middleware

3. **File Processing Layer**
   - Import session tracking
   - Data mapping between import files and database fields

4. **AI Integration Layer**
   - Template-based prompt system
   - Integration points for AI content generation services

## Performance Considerations

1. **Data Loading**
   - Pagination for large datasets
   - Lazy loading of detail views
   - Caching strategies for frequently accessed data

2. **Search and Filtering**
   - Database indexes for all searchable fields
   - Efficient query building with parameterized statements
   - Debounced search inputs to reduce server load

3. **Import Handling**
   - Background processing for large imports
   - Progress tracking and status updates
   - Error handling with detailed reporting

## Scalability Considerations

1. **Horizontal Scaling**
   - Stateless frontend architecture
   - Database connection pooling
   - Load balancing support

2. **Data Volume**
   - Efficient indexing strategy
   - Archiving capabilities for historical data
   - Partitioning strategies for large datasets

3. **User Management**
   - Role-based access control
   - User session management
   - Audit logging scalability