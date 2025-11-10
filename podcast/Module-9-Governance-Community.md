# Module 9: Governance & Community
## How AgStack Manages PANCAKE as Open-Source

**An AgStack Project of The Linux Foundation**

**Episode**: Module 9 of 10  
**Duration**: ~20 minutes  
**Prerequisites**: Episode 0  
**Technical Level**: Beginner to Intermediate

---

## Introduction

PANCAKE is not just open-source code—it's a **community-driven project** under **AgStack** governance, part of **The Linux Foundation**. This module explains how PANCAKE is managed, how decisions are made, and how you can contribute.

**What you'll learn:**
- AgStack organizational structure (TAC, TSC, Working Groups)
- Decision-making process (RFCs, voting, transparency)
- Contribution model (code, documentation, testing)
- Commercial vs community (how companies can participate)
- Conflict resolution (how disputes are handled)

**Who this is for:**
- Potential contributors (developers, farmers, vendors)
- Companies evaluating PANCAKE adoption
- Standards committee members
- Anyone interested in open-source governance

---

## Chapter 1: Organizational Structure

### Hierarchy

```
AgStack Foundation (The Linux Foundation)
    ↓
Technical Advisory Committee (TAC)
    ↓
BITE/PANCAKE Project
    ├── Technical Steering Committee (TSC)
    ├── Working Groups
    │   ├── BITE Spec WG
    │   ├── PANCAKE Implementation WG
    │   ├── TAP Adapter WG
    │   ├── SIRUP Standards WG
    │   └── SIP Protocol WG
    └── Community Contributors
```

### Roles

**1. AgStack TAC (Technical Advisory Committee)**
- Oversight for all AgStack projects (not just PANCAKE)
- Approves project charters, major direction changes
- Resolves cross-project conflicts
- **Composition**: AgStack staff + elected representatives

**2. BITE/PANCAKE TSC (Technical Steering Committee)**
- Day-to-day technical decisions
- Reviews RFCs, approves PRs
- Manages releases
- **Composition**: 5-7 elected members (meritocratic)

**3. Working Groups**
- Focus on specific components (BITE, PANCAKE, TAP, etc.)
- Propose changes, review code
- **Composition**: Anyone can join (open participation)

**4. Community Contributors**
- Code contributions (PRs)
- Documentation improvements
- Bug reports, feature requests
- **Composition**: Anyone (no barriers to entry)

---

## Chapter 2: Decision-Making Process

### RFC (Request for Comments)

**How major decisions are made**:

**Step 1**: Propose RFC
```markdown
# RFC-001: Add Support for Custom BITE Types

## Summary
Allow vendors to define custom BITE types with namespace prefixes.

## Motivation
Vendors need to extend BITE for proprietary data formats.

## Proposed Solution
- Format: `vendor:custom_type` (e.g., `leaf_agriculture:yield_prediction`)
- Validation: PANCAKE accepts any type, AI can still understand via embeddings
- Documentation: Vendors document their types in TAP registry

## Alternatives Considered
1. Reject custom types (too restrictive)
2. Require TSC approval (too slow)
3. Allow any type (chosen)

## Impact
- Low risk (backward compatible)
- High value (vendor flexibility)
```

**Step 2**: Community Discussion (2 weeks)
- RFC posted to GitHub Discussions
- Community comments, questions, suggestions
- TSC members provide feedback

**Step 3**: TSC Vote
- TSC members vote (approve/reject/needs-work)
- Majority vote wins
- Results published publicly

**Step 4**: Implementation
- If approved: Implementation PRs, documentation updates
- If rejected: RFC archived, reasons documented

### Transparency

**All decisions are public**:
- ✅ RFCs: Public GitHub Discussions
- ✅ TSC meetings: Public recordings, minutes
- ✅ Votes: Public voting records
- ✅ Code reviews: Public PRs, comments

**No secret deals, no vendor favoritism.**

---

## Chapter 3: Contribution Model

### How to Contribute

**1. Code Contributions**

```bash
# Fork repository
git clone https://github.com/agstack/pancake.git
cd pancake

# Create feature branch
git checkout -b feature/my-feature

# Make changes
# ... edit code ...

# Submit PR
git push origin feature/my-feature
# Create PR on GitHub
```

**PR Process**:
1. Submit PR with description
2. Automated tests run (CI/CD)
3. TSC member reviews
4. Address feedback
5. TSC approves → merged

**2. Documentation**

```bash
# Edit documentation
vim docs/MODULE.md

# Submit PR
git commit -m "docs: Fix typo in BITE spec"
git push
```

**3. Testing**

```bash
# Write tests
vim tests/test_bite.py

# Run tests
pytest tests/

# Submit PR with tests
```

**4. Bug Reports**

```markdown
# GitHub Issue
Title: BITE validation fails for nested JSON

Description:
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment (OS, Python version, etc.)
```

### Meritocracy

**Contributions earn influence**:
- More contributions → More recognition
- Quality contributions → TSC consideration
- **Not money-based**: Companies can't buy influence

**Example**: Developer contributes 10 PRs, fixes 5 bugs → Considered for TSC election

---

## Chapter 4: Commercial vs Community

### The Hybrid Model (Option C)

**PANCAKE Core**: Free (open-source, Apache 2.0)
**PANCAKE Enterprise**: Proprietary add-ons (companies can charge)

**Example**:
```yaml
# PANCAKE Core (free)
pancake_core:
  license: Apache 2.0
  cost: $0
  features:
    - BITE/SIP/MEAL storage
    - TAP adapter framework
    - Multi-pronged RAG
    - Basic AI queries

# PANCAKE Enterprise (proprietary)
pancake_enterprise:
  license: Proprietary
  cost: $500/month
  features:
    - Advanced analytics (proprietary algorithms)
    - Custom AI models (vendor-trained)
    - White-label branding
    - Priority support
```

**Benefits**:
- Core stays free (open-source)
- Companies make money (proprietary add-ons)
- Sustainable funding (not dependent on donations)

### Vendor Participation

**Vendors can participate**:
- ✅ Contribute code (TAP adapters, bug fixes)
- ✅ Sponsor development (fund features)
- ✅ Build on PANCAKE (commercial products)
- ❌ Control project (no single vendor controls TSC)

**Example**: Terrapipe.io contributes TAP adapter
- Terrapipe writes adapter (open-source)
- Terrapipe benefits (listed in TAP registry, more customers)
- Community benefits (one more vendor integrated)

---

## Chapter 5: Conflict Resolution

### Dispute Process

**Step 1**: Discussion (GitHub Discussions, TSC meetings)
- Raise concern publicly
- Community discusses
- Try to reach consensus

**Step 2**: TSC Mediation
- If consensus fails, TSC mediates
- TSC members hear both sides
- TSC proposes solution

**Step 3**: Vote
- If mediation fails, TSC votes
- Majority vote wins
- Results published

**Step 4**: Appeal (rare)
- If TSC decision contested, appeal to AgStack TAC
- TAC reviews, makes final decision
- Rarely needed (most disputes resolved at TSC level)

### Code of Conduct

**PANCAKE follows Linux Foundation Code of Conduct**:
- Be respectful
- Be inclusive
- Be collaborative
- No harassment, discrimination

**Violations**: Report to TSC, TSC investigates, takes action

---

## Chapter 6: Getting Involved

### For Developers

**1. Join Working Group**
```bash
# Join PANCAKE Implementation WG
# - Attend weekly meetings (public)
# - Review PRs
# - Propose features
```

**2. Contribute Code**
```bash
# Pick an issue
# - Fix bug
# - Add feature
# - Improve tests
```

**3. Run for TSC**
```markdown
# After 6+ months of contributions
# - Nominate yourself
# - Community votes
# - Top 5-7 become TSC members
```

### For Farmers

**1. Report Bugs**
```markdown
# GitHub Issue
"PANCAKE query returns wrong results for my field"
```

**2. Request Features**
```markdown
# GitHub Discussion
"I need EUDR compliance reports for my cooperative"
```

**3. Test Beta Releases**
```bash
# Install beta version
pip install pancake==2.0.0-beta1

# Test, report feedback
```

### For Vendors

**1. Build TAP Adapter**
```python
# Implement TAP adapter
class MyVendorAdapter(TAPAdapter):
    ...

# Submit PR
# - Adapter reviewed
# - Added to TAP registry
# - Available to all PANCAKE users
```

**2. Sponsor Development**
```yaml
# Sponsor a feature
sponsor:
  feature: "EUDR compliance module"
  amount: $10,000
  timeline: "Q2 2025"
```

**3. Join TSC**
```markdown
# After significant contributions
# - Nominate vendor representative
# - Community votes
# - Vendor gets TSC seat (merit-based, not money-based)
```

---

## Conclusion

**PANCAKE governance is**:
- ✅ **Transparent**: All decisions public
- ✅ **Meritocratic**: Contributions earn influence
- ✅ **Vendor-neutral**: No single company controls it
- ✅ **Sustainable**: Hybrid model (free core + paid add-ons)
- ✅ **Inclusive**: Anyone can contribute

**The result**: PANCAKE is truly open-source infrastructure, managed by the community, for the community.

**Next module**: POC Results & Road Ahead - What's been built, what's next.

---

**An AgStack Project | Powered by The Linux Foundation**

**Learn more**: https://agstack.org/pancake  
**GitHub**: https://github.com/agstack/pancake  
**License**: Apache 2.0 (Code) | CC BY 4.0 (Documentation)

