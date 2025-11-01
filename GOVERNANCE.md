# GOVERNANCE: AgStack Open Source Model

**Project**: BITE/PANCAKE/TAP/SIRUP/SIP  
**Organization**: AgStack  
**License**: Apache 2.0  
**Version**: 1.0  
**Last Updated**: November 2024

---

## Table of Contents

1. [Overview](#overview)
2. [Mission & Values](#mission--values)
3. [Organizational Structure](#organizational-structure)
4. [Decision-Making Process](#decision-making-process)
5. [Contribution Model](#contribution-model)
6. [Membership & Funding](#membership--funding)
7. [Technical Steering Committee](#technical-steering-committee)
8. [RFC Process](#rfc-process)
9. [Repository Structure](#repository-structure)
10. [Release Process](#release-process)
11. [Commercial vs Community](#commercial-vs-community)
12. [Conflict Resolution](#conflict-resolution)

---

## Overview

The BITE/PANCAKE ecosystem is an **open-source initiative** under **AgStack** governance. This document defines how the project is managed, how decisions are made, and how the community contributes.

### Key Principles

1. **Vendor Neutral**: No single company controls the project
2. **Community Driven**: Decisions made transparently via RFC process
3. **Open Governance**: All meetings, votes, and discussions are public
4. **Meritocratic**: Contributions earn influence, not money
5. **Sustainable**: Funded by AgStack membership, not vendor lock-in

---

## Mission & Values

### Mission Statement

**"Enable global agricultural data interoperability through open, AI-native standards."**

### Core Values

**1. Interoperability Over Optimization**
- Standards that work everywhere > proprietary formats
- Farmer data portability > vendor lock-in

**2. Simplicity Over Perfection**
- Adoption > elegance
- "Worse is better" philosophy (pragmatic design)

**3. Transparency Over Control**
- Public roadmap, public RFCs, public votes
- No secret vendor deals

**4. Sustainability Over Speed**
- Long-term viability > short-term hype
- 10-year vision, not 10-month MVP

**5. Accessibility Over Exclusivity**
- Designed for global use (not just US/EU)
- Works offline, low-cost, low-bandwidth

---

## Organizational Structure

### Hierarchy

```
AgStack Foundation
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
- Oversight for all AgStack projects (not just BITE/PANCAKE)
- Approves project charters, major direction changes
- Resolves cross-project conflicts
- **Composition**: AgStack staff + elected representatives

**2. BITE/PANCAKE TSC (Technical Steering Committee)**
- Day-to-day governance of BITE/PANCAKE project
- Approves RFCs, reviews PRs, manages releases
- **Composition**: 7 members (elected by community)
- **Term**: 2 years (staggered)

**3. Working Group Leads**
- Focus on specific areas (BITE spec, TAP adapters, etc.)
- Report to TSC
- **Elected by WG members** (annual)

**4. Maintainers**
- Commit access to repositories
- Code review, merge PRs, triage issues
- **Appointed by TSC** (based on contributions)

**5. Contributors**
- Anyone who submits PRs, issues, RFCs
- No membership required (open to all)

---

## Decision-Making Process

### RFC (Request for Comments) Process

**All significant changes require an RFC.**

**What needs an RFC**:
- Changes to BITE/PANCAKE/TAP/SIRUP/SIP specifications
- New BITE types
- Breaking changes
- Major feature additions
- Governance changes

**What doesn't need an RFC**:
- Bug fixes
- Documentation improvements
- Performance optimizations (no spec change)
- Test additions

### RFC Workflow

**1. Author writes RFC**
```markdown
# RFC-NNN: Title

## Summary
One-paragraph explanation.

## Motivation
Why is this needed?

## Detailed Design
How will it work?

## Drawbacks
What are the downsides?

## Alternatives
What other approaches were considered?

## Unresolved Questions
What needs to be figured out?
```

**2. Submit as PR** to `agstack/bite-rfcs` repo

**3. Community Discussion** (2-4 weeks)
- Open to all (GitHub comments, mailing list, meetings)
- RFC author responds to feedback, updates RFC

**4. TSC Review** (bi-weekly meeting)
- TSC discusses, may request changes
- **Vote**: Approve, Reject, or Defer
- **Quorum**: 4 of 7 TSC members
- **Threshold**: Simple majority (4 votes)

**5. Final Comment Period** (1 week)
- If approved, RFC enters FCP (last chance for objections)
- If no major concerns, RFC is **accepted**

**6. Implementation**
- RFC author (or volunteer) implements
- Code reviewed by maintainers
- Merged when ready

**7. Documentation**
- Update specs, examples, tutorials
- Announce in release notes

### Voting Rules

**RFC Votes**:
- **Approve**: RFC is good, implement it
- **Approve with changes**: RFC is good after edits
- **Defer**: Not ready, needs more work
- **Reject**: Fundamental issues, won't implement

**TSC Member Votes**:
- Each member has 1 vote
- Abstain allowed (doesn't count toward quorum)
- Public votes (recorded in meeting notes)

---

## Contribution Model

### How to Contribute

**1. Code Contributions**
- Fork repo → Branch → Code → PR → Review → Merge
- Sign **Developer Certificate of Origin (DCO)** (git commit -s)
- Follow code style (linters, tests, docs)

**2. Specification Contributions**
- Propose changes via RFC
- Discuss in working groups
- TSC approves

**3. Adapter Contributions**
- Build TAP adapter for vendor
- Submit to `agstack/tap-adapters`
- Maintainer reviews, publishes to registry

**4. Documentation Contributions**
- Tutorials, examples, translations
- Submit PRs to `agstack/docs`

**5. Community Contributions**
- Answer questions (GitHub Issues, forums)
- Triage bugs, reproduce issues
- Evangelize (blog posts, talks, workshops)

### Contributor Levels

**Level 0: Observer**
- Reads docs, uses BITE/PANCAKE
- No formal role

**Level 1: Contributor**
- Submits PRs, files issues, participates in RFCs
- Recognition: Listed in CONTRIBUTORS.md

**Level 2: Maintainer**
- Commit access, code review, merge PRs
- **Requirements**:
  - 6+ months of contributions
  - 10+ merged PRs
  - Nominated by existing maintainer
  - Approved by TSC

**Level 3: TSC Member**
- Governance, RFC approval, release management
- **Requirements**:
  - 1+ year as maintainer
  - Significant contributions (code, docs, community)
  - Elected by community (annual vote)

---

## Membership & Funding

### AgStack Membership

**BITE/PANCAKE is part of AgStack**, a broader initiative for agricultural open source.

**Membership Tiers** (AgStack-wide):

**1. Community Tier** (Free)
- Access to all open-source projects
- Participate in RFCs, contribute code
- No voting rights

**2. Member Tier** ($10K/year)
- All community benefits
- Voting rights (elect TSC)
- Priority support (AgStack staff)
- Logo on AgStack website

**3. Sponsor Tier** ($50K/year)
- All member benefits
- Seat on AgStack TAC (advisory)
- Influence roadmap (but not control)
- Co-marketing opportunities

**4. Platinum Tier** ($100K+/year)
- All sponsor benefits
- Dedicated AgStack liaison
- Custom workshops, training

### Funding Allocation

**AgStack membership fees** fund:
- **Staff**: Technical writers, community managers, DevOps
- **Infrastructure**: GitHub org, CI/CD, hosting, domain names
- **Events**: Conferences, hackathons, meetups
- **Grants**: Student projects, research collaborations

**NOT funded by membership**:
- Development (volunteer/contributor-driven)
- Vendor-specific features (build yourself or hire devs)

### Commercial Offerings

**Community version** (open-source, free):
- All code on GitHub
- Self-hosted
- Community support (forums, GitHub Issues)

**Commercial versions** (third-party vendors):
- **Hosted PANCAKE** (e.g., "PANCAKE Cloud" by Vendor X)
  - SaaS deployment, managed infrastructure
  - Pricing: Vendor sets (e.g., $50-500/month)
  - Uses open-source PANCAKE under Apache 2.0
- **Enterprise support** (e.g., consulting, SLAs)
- **Custom integrations** (e.g., vendor-specific adapters)

**Important**: Vendors can commercialize, but:
- Must respect Apache 2.0 license (attribution)
- Cannot claim endorsement by AgStack (without permission)
- Cannot use "AgStack" trademark without license

---

## Technical Steering Committee

### Composition

**7 members**, elected by community:
- **3 seats**: Technical experts (developers, researchers)
- **2 seats**: Vendor representatives (ag-tech companies)
- **2 seats**: End-user representatives (farmers, co-ops, NGOs)

**Current TSC** (as of Nov 2024): *To be elected*

### Responsibilities

**1. Specification Stewardship**
- Approve RFCs for BITE/PANCAKE/TAP/SIRUP/SIP specs
- Ensure consistency across specifications
- Deprecate old features (with migration path)

**2. Release Management**
- Decide release schedule (semantic versioning)
- Approve breaking changes (major versions)
- Coordinate cross-repo releases

**3. Maintainer Oversight**
- Appoint maintainers (based on contributions)
- Remove maintainers (inactivity, code of conduct violations)
- Resolve maintainer disputes

**4. Community Health**
- Enforce code of conduct
- Foster inclusive, welcoming environment
- Organize events, outreach

**5. Strategic Direction**
- Set roadmap (based on community input)
- Prioritize features (not dictate, but guide)
- Liaise with AgStack TAC

### Meetings

**Frequency**: Bi-weekly (every 2 weeks)  
**Duration**: 1 hour  
**Format**: Video call (Zoom, Google Meet)  
**Notes**: Public (posted to GitHub)  
**Attendance**: Public (anyone can observe)

**Agenda**:
1. Review pending RFCs (vote if ready)
2. Discuss issues/PRs (escalated by maintainers)
3. Release planning
4. Community updates

---

## RFC Process

### RFC Template

**File**: `rfcs/NNN-title.md`

```markdown
# RFC-NNN: [Title]

- **Start Date**: YYYY-MM-DD
- **Author(s)**: @github-handle
- **Status**: Draft | In Review | Accepted | Rejected | Implemented

## Summary

One-paragraph explanation of the feature/change.

## Motivation

Why are we doing this? What use cases does it support?

## Guide-Level Explanation

Explain the proposal as if it were already implemented and you were teaching it to users.

## Reference-Level Explanation

This is the technical portion. Explain the design in sufficient detail that:
- Its interaction with other features is clear
- It is reasonably clear how the feature would be implemented
- Corner cases are dissected by example

## Drawbacks

Why should we *not* do this?

## Rationale and Alternatives

- Why is this design the best in the space of possible designs?
- What other designs have been considered and what is the rationale for not choosing them?
- What is the impact of not doing this?

## Prior Art

Discuss prior art from other projects (e.g., how do GeoJSON, ADAPT, etc. handle this?).

## Unresolved Questions

What parts of the design are still TBD?

## Future Possibilities

What future work could build on this?
```

### RFC Lifecycle

**Draft** → **In Review** (TSC discussing) → **FCP** (final comment period) → **Accepted** or **Rejected** → **Implemented**

**Timeline**:
- Draft: Anytime (author writes)
- In Review: 2-4 weeks (community feedback)
- FCP: 1 week (last call for objections)
- Decision: TSC vote (at bi-weekly meeting)
- Implementation: Weeks to months (depends on complexity)

---

## Repository Structure

### GitHub Organization

**`github.com/agstack/`**

```
agstack/
├── bite-spec/              # BITE specification (Markdown)
├── pancake/                # PANCAKE reference implementation (Python)
├── tap-core/               # TAP framework (Python)
├── tap-adapters/           # Community TAP adapters
│   ├── terrapipe/
│   ├── planet/
│   ├── cropx/
│   └── ...
├── sirup-schemas/          # SIRUP type definitions (JSON Schema)
├── sip-spec/               # SIP specification (Markdown)
├── bite-rfcs/              # RFCs for spec changes
├── docs/                   # Tutorials, guides, examples
├── tools/                  # CLI tools (bite-cli, tap-cli, pancake-cli)
└── website/                # Public website (documentation portal)
```

### Repository Permissions

**Public Read**: Anyone (open-source)  
**Write Access**: Maintainers only  
**Admin Access**: TSC members + AgStack staff

---

## Release Process

### Versioning

**Semantic Versioning** (SemVer): `MAJOR.MINOR.PATCH`

**MAJOR**: Breaking changes (e.g., BITE v2.0)  
**MINOR**: New features (backward-compatible)  
**PATCH**: Bug fixes, documentation

**Example**:
- BITE v1.0.0 (initial release)
- BITE v1.1.0 (add new optional field to Header)
- BITE v1.1.1 (fix documentation typo)
- BITE v2.0.0 (change hash algorithm, breaking)

### Release Schedule

**Cadence**: Time-based (every 3 months) + on-demand (for critical fixes)

**Q1 2025**: v1.1.0  
**Q2 2025**: v1.2.0  
**Q3 2025**: v1.3.0  
**Q4 2025**: v2.0.0 (if breaking changes needed)

### Release Process

**1. Feature Freeze** (2 weeks before release)
- No new features, only bug fixes
- Stabilize, test, document

**2. Release Candidate** (1 week before release)
- Tag `v1.2.0-rc1`
- Community testing, feedback
- Fix critical bugs (if any)

**3. Release**
- Tag `v1.2.0`
- Publish to package managers (PyPI, npm, etc.)
- Announce (blog post, mailing list, social media)

**4. Post-Release**
- Monitor issues, respond to feedback
- Patch releases (v1.2.1, v1.2.2) as needed

---

## Commercial vs Community

### Clear Separation

**Community Edition** (Open-Source):
- **License**: Apache 2.0 (free, open)
- **Code**: All on GitHub (github.com/agstack)
- **Support**: Community (forums, GitHub Issues)
- **Hosting**: Self-hosted (your infrastructure)

**Commercial Offerings** (Third-Party Vendors):
- **Hosted PANCAKE**: SaaS by vendors (e.g., "PANCAKE Cloud")
- **Enterprise Support**: SLAs, consulting, training
- **Custom Features**: Vendor-specific extensions

**Example Vendors**:
- "FarmTech Co" offers "PANCAKE Cloud" (hosted)
  - Uses open-source PANCAKE (Apache 2.0)
  - Adds proprietary UI, integrations
  - Charges $100/month
  - **Allowed** (Apache 2.0 permits this)
  - **Must**: Attribute AgStack, respect license

### Vendor Obligations

**If you commercialize BITE/PANCAKE**:
1. **Attribution**: Include Apache 2.0 license text, credit AgStack
2. **No Endorsement**: Can't claim AgStack endorses your product (without permission)
3. **Trademark**: Can't use "AgStack" in product name (without license)
4. **Open-Source Contributions**: Encouraged to contribute back (but not required)

**AgStack Encourages**:
- Contributing bug fixes upstream
- Sharing adapters (so others benefit)
- AgStack membership (funding sustainability)

**AgStack Does NOT Require**:
- Revenue sharing (keep your profits)
- Open-sourcing proprietary extensions
- Using AgStack branding

---

## Conflict Resolution

### Code of Conduct

**All contributors must follow the AgStack Code of Conduct.**

**Summary**:
- Be respectful, inclusive, welcoming
- No harassment, discrimination, personal attacks
- Disagree constructively (critique ideas, not people)

**Enforcement**: Code of Conduct Committee (CoCC) handles violations

### Dispute Resolution

**Technical Disputes** (e.g., RFC disagreements):
1. Discussion (GitHub, mailing list, meetings)
2. TSC vote (if no consensus)
3. TSC decision is final

**Interpersonal Disputes** (e.g., maintainer conflicts):
1. Private mediation (CoCC)
2. Warning (first offense)
3. Temporary suspension (repeated offenses)
4. Permanent ban (egregious violations)

**Vendor Disputes** (e.g., two vendors want conflicting features):
1. Both submit RFCs (present use cases)
2. Community discussion (pros/cons)
3. TSC evaluates (based on merit, alignment with mission)
4. TSC votes (majority wins)
5. **No vendor veto** (can't block because it helps competitor)

---

## Conclusion

The BITE/PANCAKE ecosystem thrives through **open governance**:
- Transparent decision-making (RFC process)
- Community-driven (meritocracy)
- Vendor-neutral (no single company controls)
- Sustainable (AgStack membership funding)

**Get Involved**:
- **Contribute**: Submit PRs, write RFCs
- **Participate**: Join working groups, attend meetings
- **Support**: Become AgStack member (if organization)

**The future of agricultural data is open, collaborative, and community-owned.** 🌱

---

**Document Status**: Governance v1.0  
**Effective Date**: January 1, 2025  
**Next Review**: January 1, 2026  
**Contact**: governance@agstack.org  
**License**: CC BY 4.0 (this document)

