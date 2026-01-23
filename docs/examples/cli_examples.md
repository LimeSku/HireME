# Example usage with HireME - CLI

## Job agent
### Extract one or more job offer in structured way

**Command:**

```bash
hireme job "Python Developer" --location "Paris" --max-results-per-source 5
```
**Output (cropped to one) :**
```json
{
  "title": "Senior Software Engineer (AI Startup)",
  "company": {
    "name": "Noota",
    "industry": "AI, Productivity Solutions",
    "size": "Unknown",
    "description": "Noota is a sovereign 360 AI productivity solution. They are the leaders in AI note-taking in France and are currently launching their European implementation.",
    "culture_keywords": [
      "fast-growing",
      "innovation",
      "collaborative",
      "exciting technical challenges"
    ]
  },
  "location": "75008 Paris, France",
  "work_mode": "Hybrid",
  "contract_type": "CDI",
  "experience_level": "Senior (5-10 years)",
  "start_date": null,
  "salary": {
    "min_amount": 40000,
    "max_amount": 70000,
    "currency": "EUR",
    "period": "yearly",
    "is_gross": true
  },
  "benefits": [
    "Intéressement et participation"
  ],
  "required_skills": [
    {
      "name": "Python backend development",
      "level": "required",
      "years_experience": 5
    },
    {
      "name": "API design and implementation with FastAPI",
      "level": "preferred",
      "years_experience": 3
    },
    {
      "name": "Kubernetes and Docker experience",
      "level": "required",
      "years_experience": 3
    },
    {
      "name": "Infrastructure as code tools like Terraform",
      "level": "required",
      "years_experience": 2
    },
    {
      "name": "Experience with various database systems (SQL, NoSQL, PostgreSQL)",
      "level": "required",
      "years_experience": 5
    },
    {
      "name": "Familiarity with monitoring tools such as Prometheus, Grafana, and the ELK stack",
      "level": "preferred",
      "years_experience": 3
    },
    {
      "name": "Experience with messaging queues/Pub/Sub systems",
      "level": "required",
      "years_experience": 2
    },
    {
      "name": "Proven experience in scaling environments and working with cloud providers (Scaleway, Azure)",
      "level": "required",
      "years_experience": 5
    },
    {
      "name": "Leadership potential",
      "level": "preferred",
      "years_experience": null
    }
  ],
  "required_languages": [],
  "required_education": null,
  "responsibilities": [
    "Backend Development: Design, develop, and optimize high-performance, scalable, and secure backend services primarily using Python, with a focus on FastAPI.",
    "Architectural Contribution: Actively participate in the architectural design and evolution of our microservices-based platform, ensuring its scalability, resilience, and maintainability.",
    "DevOps & Infrastructure: Work with containerization (Docker), orchestration (Kubernetes), and infrastructure as code (Terraform) to manage and deploy our applications across cloud environments (Scaleway, Azure).",
    "Data Management: Design and implement efficient data storage solutions using both SQL (PostgreSQL) and NoSQL databases, as well as caching mechanisms (Redis).",
    "Monitoring & Observability: Implement and manage monitoring and alerting systems using tools like Prometheus, Grafana, and the ELK stack to ensure the health and performance of our systems.",
    "Messaging Systems: Utilize Pub/Sub patterns for asynchronous communication and event-driven architectures.",
    "Security & Sovereignty: Contribute to building and maintaining a sovereign and secure platform, adhering to best practices and Noota's commitment to data privacy.",
    "Technical Leadership: Mentor junior developers, conduct code reviews, and foster a culture of technical excellence and continuous improvement.",
    "Problem Solving: Diagnose and resolve complex technical issues across the entire stack in a fast-paced, scaling environment.",
    "Innovation: Stay abreast of new technologies and industry trends, proposing and implementing innovative solutions to enhance Noota's product offering."
  ],
  "team_info": null,
  "reports_to": null,
  "application_deadline": null,
  "application_url": null,
  "contact_email": null,
  "key_selling_points": [
    "Join a fast-growing company at the forefront of AI innovation and a leader in its market.",
    "A stimulating and collaborative work environment where your technical expertise and leadership will have a direct and significant impact.",
    "Exciting technical challenges, working on a diverse range of cutting-edge technologies and architectural patterns.",
    "Clear path for career progression towards a Tech Lead role with opportunities for mentorship and technical ownership."
  ],
  "potential_challenges": [
    "Highly competitive startup environment",
    "Fast-paced scaling requirements"
  ]
}
```

## Resume agent
### Init .hireme/ and populate with informations template

**Command:**

```bash
hireme resume init
```
**Output:**
```
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Profile directory created: /path/to/HireME/.hireme/profile                                                                                                       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
Created files:
  - /path/to/HireME/.hireme/profile/context.md
  - /path/to/HireME/.hireme/profile/profile.yaml

Next steps:
1. Edit context.md with your real information
2. Edit profile.yaml with your contact details
3. Add any PDF resumes or additional documents
```

### Generate a tailored resume for each job offer !

**Command:**
```bash
hireme resume generate --job-dir .hireme/job_offers/ --output-dir output/
```

**Output (cropped):**

```
2026-01-20 21:37:36 [info ] Resume PDF generated    agent=resume_agent  path=output/resume_3/jean_dupont_cv.pdf
✓ Resume generated successfully!
PDF saved to: output/resume_3/jean_dupont_cv.pdf
```
And the **output** of the tree command in the output/ directory:
```
output
├── resume_0
│   ├── julien_dubois_cv.pdf
│   ├── julien_dubois_cv.typ
│   └── julien_dubois_cv.yaml
├── resume_1
│   ├── jean_dupont_cv.pdf
│   ├── jean_dupont_cv.typ
│   └── jean_dupont_cv.yaml
├── resume_2
│   ├── julien_dupont_cv.pdf
│   ├── julien_dupont_cv.typ
│   └── julien_dupont_cv.yaml
└── resume_3
    ├── jean_dupont_cv.pdf
    ├── jean_dupont_cv.typ
    └── jean_dupont_cv.yaml

5 directories, 12 files
```