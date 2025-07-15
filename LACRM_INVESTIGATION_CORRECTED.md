# LACRM API Investigation Results - CORRECTED

## Updated Documentation: Companies in LACRM

### Key Findings ✅

The user was **CORRECT** - there ARE companies in LACRM. The issue was with our understanding of how LACRM stores and represents company data.

### LACRM Data Structure (Corrected Understanding)

#### 1. Company Records (`IsCompany=1`)
- **4 company records** found with `IsCompany="1"`
- These are actual company entities in LACRM
- Company names stored in `CompanyName` field
- Examples: "Hjerteveien", "GJS Trafikkskole AS", "GJS Trafikkskole i Moss og Vestby", "AS Husselskapet"

#### 2. Individual Contacts with Company Association
- **1 individual contact** linked to a company
- Has `IsCompany="0"` but has `CompanyName` populated
- Example: "Terje" working at "Trollhagen AS"

#### 3. Individual Contacts (No Company)
- **20 individual contacts** with no company association
- `IsCompany="0"` and `CompanyName=null`

### API Limitations Discovered

#### Working Functions ✅
- `SearchContacts` - Returns all contacts (both individuals and companies)
- `GetCustomFields` - Returns custom field definitions

#### Non-Working Functions ❌
- `GetCompanies` - Returns 400 Bad Request
- `SearchCompanies` - Returns 400 Bad Request  
- `GetCompany` - Returns 400 Bad Request
- `GetContacts` - Returns 400 Bad Request

**Conclusion**: The API has limited permissions - only contact search functions work, but companies are stored as contacts with `IsCompany="1"`.

### Script Updates Made

#### 1. Added `get_lacrm_companies()` Function
```python
def get_lacrm_companies(config):
    """Fetches company records from LACRM using SearchContacts with IsCompany=1 filter."""
    # Get all contacts, then filter for:
    # - Records with IsCompany="1" (actual company records)
    # - Records with CompanyName populated (individuals linked to companies)
```

#### 2. Updated `sync_all_lacrm_contacts()` Function
- Now processes **both** company records and individual contacts with company associations
- Determines company name based on record type:
  - For `IsCompany="1"`: Use `CompanyName` or fallback to `FirstName`
  - For individuals: Use `CompanyName` field
- Proper handling of 5 company records found

#### 3. Custom Fields Status
- **0 custom fields** returned by API despite user claiming they exist
- This suggests either:
  - Custom fields not properly configured
  - API permissions don't include custom field access
  - Fields exist but aren't accessible via this API endpoint

### Current Processing Status

#### Companies Ready for Processing: **5 total**
1. **Trollhagen AS** (Individual contact with company association)
2. **Hjerteveien** (Company record, IsCompany=1)
3. **GJS Trafikkskole AS** (Company record, IsCompany=1) 
4. **GJS Trafikkskole i Moss og Vestby** (Company record, IsCompany=1)
5. **AS Husselskapet** (Company record, IsCompany=1)

#### Organization Numbers: **0 found**
- All companies need organization number lookup from Brønnøysund
- Script can use `find_orgnr_by_name()` function for this

### Next Steps

1. **✅ COMPLETED**: Updated script to properly identify companies
2. **🔄 PENDING**: Resolve DNS module import error to test full functionality
3. **🔄 PENDING**: Test organization number lookup for the 5 companies
4. **🔄 PENDING**: Investigate custom fields discrepancy

### Validation Command
```bash
python test_corrected_approach.py
```

### Test Single Company Processing
```bash
python lacrm_sync.py --oppdater [company_orgnr_when_found]
```

## Status: CORRECTED ✅

The script now properly identifies and can process **5 companies** in LACRM, contradicting the earlier assumption that only individual contacts existed. The API limitation is in accessing company-specific endpoints, but companies exist as searchable contact records with `IsCompany="1"`.
