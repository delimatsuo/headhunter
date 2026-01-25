/**
 * Skills Master Database - Single Source of Truth
 *
 * Copied from EllaAI: react-spa/src/data/skills-master.ts
 * Date: 2026-01-25
 *
 * This is a local copy for Headhunter customization and independence.
 * Contains 200+ skills with aliases, categories, and market data.
 */

/**
 * MASTER SKILLS DATABASE - Single Source of Truth
 *
 * This file is the ONLY authoritative source for skills in the application.
 * All components MUST import skills from here, never define their own lists.
 *
 * Used by:
 * - Career Explorer (skill requirements per career)
 * - Skills Center (add skill manually dropdown)
 * - Resume Import (skill matching)
 * - Job Matching (skill comparison)
 * - Skill Certification (available certifications)
 *
 * Based on:
 * - O*NET Content Model
 * - LinkedIn Skills Graph
 * - ESCO (European Skills/Competences)
 * - Industry standard job requirements
 */

// ============================================================================
// TYPES
// ============================================================================

export type SkillCategory =
    | 'programming-languages'
    | 'web-frameworks'
    | 'mobile-development'
    | 'cloud-devops'
    | 'databases'
    | 'data-engineering'
    | 'machine-learning'
    | 'security'
    | 'testing-qa'
    | 'architecture'
    | 'design-ux'
    | 'product-management'
    | 'leadership'
    | 'communication'
    | 'business';

export interface Skill {
    id: string;
    name: string;
    category: SkillCategory;
    aliases?: string[]; // Alternative names for matching
    certifiable: boolean; // Can this skill be certified?
    description?: string;
    // Market data for ROI calculation (gap analysis)
    marketDemand: 'low' | 'medium' | 'high' | 'critical';
    trendDirection: 'declining' | 'stable' | 'growing' | 'emerging';
    avgSalaryImpact?: number; // Percentage salary increase for this skill
    relatedSkillIds?: string[]; // Complementary skills
    tags?: string[]; // For filtering and categorization
}

export interface SkillCategoryMeta {
    id: SkillCategory;
    name: string;
    shortName: string;
    icon: string; // MUI icon name
    color: string;
    description: string;
}

// ============================================================================
// SKILL CATEGORIES
// ============================================================================

export const SKILL_CATEGORIES: SkillCategoryMeta[] = [
    {
        id: 'programming-languages',
        name: 'Programming Languages',
        shortName: 'Languages',
        icon: 'Code',
        color: '#3B82F6',
        description: 'Core programming and scripting languages'
    },
    {
        id: 'web-frameworks',
        name: 'Web Frameworks & Libraries',
        shortName: 'Web/Frameworks',
        icon: 'Web',
        color: '#8B5CF6',
        description: 'Frontend and backend frameworks'
    },
    {
        id: 'mobile-development',
        name: 'Mobile Development',
        shortName: 'Mobile',
        icon: 'PhoneIphone',
        color: '#84CC16',
        description: 'iOS, Android, and cross-platform'
    },
    {
        id: 'cloud-devops',
        name: 'Cloud & DevOps',
        shortName: 'Cloud/DevOps',
        icon: 'Cloud',
        color: '#06B6D4',
        description: 'Cloud platforms, CI/CD, infrastructure'
    },
    {
        id: 'databases',
        name: 'Databases',
        shortName: 'Databases',
        icon: 'Storage',
        color: '#F59E0B',
        description: 'SQL, NoSQL, and data storage'
    },
    {
        id: 'data-engineering',
        name: 'Data Engineering',
        shortName: 'Data Eng',
        icon: 'AccountTree',
        color: '#14B8A6',
        description: 'Data pipelines, ETL, analytics'
    },
    {
        id: 'machine-learning',
        name: 'Machine Learning & AI',
        shortName: 'ML/AI',
        icon: 'Psychology',
        color: '#EC4899',
        description: 'ML, deep learning, AI systems'
    },
    {
        id: 'security',
        name: 'Security',
        shortName: 'Security',
        icon: 'Security',
        color: '#EF4444',
        description: 'Cybersecurity, compliance, risk'
    },
    {
        id: 'testing-qa',
        name: 'Testing & QA',
        shortName: 'Testing',
        icon: 'BugReport',
        color: '#22C55E',
        description: 'Testing, quality assurance'
    },
    {
        id: 'architecture',
        name: 'Architecture & Design',
        shortName: 'Architecture',
        icon: 'Architecture',
        color: '#F97316',
        description: 'System design, patterns, scalability'
    },
    {
        id: 'design-ux',
        name: 'Design & UX',
        shortName: 'Design',
        icon: 'Palette',
        color: '#A855F7',
        description: 'UI/UX design, user research'
    },
    {
        id: 'product-management',
        name: 'Product Management',
        shortName: 'Product',
        icon: 'Inventory2',
        color: '#FF5722',
        description: 'Product strategy, roadmapping'
    },
    {
        id: 'leadership',
        name: 'Leadership & Management',
        shortName: 'Leadership',
        icon: 'Groups',
        color: '#6366F1',
        description: 'People management, mentoring'
    },
    {
        id: 'communication',
        name: 'Communication',
        shortName: 'Communication',
        icon: 'Chat',
        color: '#0EA5E9',
        description: 'Written, verbal, presentation'
    },
    {
        id: 'business',
        name: 'Business & Strategy',
        shortName: 'Business',
        icon: 'TrendingUp',
        color: '#64748B',
        description: 'Business acumen, strategy'
    }
];

// ============================================================================
// MASTER SKILLS LIST
// ============================================================================

export const MASTER_SKILLS: Skill[] = [
    // =========================================================================
    // PROGRAMMING LANGUAGES
    // =========================================================================
    { id: 'javascript', name: 'JavaScript', category: 'programming-languages', certifiable: true, aliases: ['JS', 'ECMAScript'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['typescript', 'react', 'nodejs'], tags: ['programming', 'web', 'frontend', 'backend'] },
    { id: 'typescript', name: 'TypeScript', category: 'programming-languages', certifiable: true, aliases: ['TS'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['javascript', 'react', 'nodejs'], tags: ['programming', 'web', 'typed'] },
    { id: 'python', name: 'Python', category: 'programming-languages', certifiable: true, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 20, relatedSkillIds: ['django', 'ml-fundamentals', 'data-analysis'], tags: ['programming', 'backend', 'data', 'ml'] },
    { id: 'java', name: 'Java', category: 'programming-languages', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['spring-boot', 'kotlin'], tags: ['programming', 'backend', 'enterprise'] },
    { id: 'go', name: 'Go', category: 'programming-languages', certifiable: true, aliases: ['Golang'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['kubernetes', 'docker'], tags: ['programming', 'backend', 'cloud', 'systems'] },
    { id: 'rust', name: 'Rust', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'emerging', avgSalaryImpact: 25, relatedSkillIds: ['cpp'], tags: ['programming', 'systems', 'performance'] },
    { id: 'csharp', name: 'C#', category: 'programming-languages', certifiable: true, aliases: ['CSharp', 'C Sharp'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 17, relatedSkillIds: ['dotnet'], tags: ['programming', 'backend', 'enterprise'] },
    { id: 'cpp', name: 'C++', category: 'programming-languages', certifiable: true, aliases: ['CPP'], marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 20, relatedSkillIds: ['rust'], tags: ['programming', 'systems', 'performance', 'embedded'] },
    { id: 'c', name: 'C', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['cpp'], tags: ['programming', 'systems', 'embedded'] },
    { id: 'ruby', name: 'Ruby', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 15, relatedSkillIds: ['rails'], tags: ['programming', 'backend', 'web'] },
    { id: 'php', name: 'PHP', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 12, relatedSkillIds: ['laravel'], tags: ['programming', 'backend', 'web'] },
    { id: 'scala', name: 'Scala', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['spark', 'java'], tags: ['programming', 'backend', 'data'] },
    { id: 'kotlin', name: 'Kotlin', category: 'programming-languages', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['java', 'android-development'], tags: ['programming', 'mobile', 'android'] },
    { id: 'swift', name: 'Swift', category: 'programming-languages', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 20, relatedSkillIds: ['ios-development', 'swiftui'], tags: ['programming', 'mobile', 'ios'] },
    { id: 'r', name: 'R', category: 'programming-languages', certifiable: true, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['statistics', 'data-analysis'], tags: ['programming', 'data', 'statistics'] },
    { id: 'sql', name: 'SQL', category: 'programming-languages', certifiable: true, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['postgresql', 'mysql', 'database-design'], tags: ['database', 'data', 'backend'] },
    { id: 'bash', name: 'Bash/Shell', category: 'programming-languages', certifiable: false, aliases: ['Shell', 'Scripting'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['linux'], tags: ['scripting', 'devops'] },
    { id: 'powershell', name: 'PowerShell', category: 'programming-languages', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['azure'], tags: ['scripting', 'windows', 'devops'] },

    // =========================================================================
    // WEB FRAMEWORKS & LIBRARIES
    // =========================================================================
    { id: 'react', name: 'React', category: 'web-frameworks', certifiable: true, aliases: ['React.js', 'ReactJS'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['javascript', 'typescript', 'nextjs'], tags: ['frontend', 'web', 'ui'] },
    { id: 'vue', name: 'Vue.js', category: 'web-frameworks', certifiable: true, aliases: ['Vue', 'VueJS'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['javascript', 'nuxt'], tags: ['frontend', 'web', 'ui'] },
    { id: 'angular', name: 'Angular', category: 'web-frameworks', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['typescript'], tags: ['frontend', 'web', 'enterprise'] },
    { id: 'svelte', name: 'Svelte', category: 'web-frameworks', certifiable: true, marketDemand: 'medium', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['javascript'], tags: ['frontend', 'web'] },
    { id: 'nextjs', name: 'Next.js', category: 'web-frameworks', certifiable: true, aliases: ['NextJS'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 20, relatedSkillIds: ['react', 'typescript'], tags: ['fullstack', 'web', 'ssr'] },
    { id: 'nuxt', name: 'Nuxt.js', category: 'web-frameworks', certifiable: false, aliases: ['NuxtJS'], marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['vue'], tags: ['fullstack', 'web', 'ssr'] },
    { id: 'nodejs', name: 'Node.js', category: 'web-frameworks', certifiable: true, aliases: ['NodeJS', 'Node'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['javascript', 'express', 'nestjs'], tags: ['backend', 'web', 'runtime'] },
    { id: 'express', name: 'Express.js', category: 'web-frameworks', certifiable: false, aliases: ['Express'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['nodejs'], tags: ['backend', 'web', 'api'] },
    { id: 'nestjs', name: 'NestJS', category: 'web-frameworks', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['nodejs', 'typescript'], tags: ['backend', 'web', 'enterprise'] },
    { id: 'django', name: 'Django', category: 'web-frameworks', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['python'], tags: ['backend', 'web', 'fullstack'] },
    { id: 'flask', name: 'Flask', category: 'web-frameworks', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['python'], tags: ['backend', 'web', 'api'] },
    { id: 'fastapi', name: 'FastAPI', category: 'web-frameworks', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['python'], tags: ['backend', 'api', 'async'] },
    { id: 'spring-boot', name: 'Spring Boot', category: 'web-frameworks', certifiable: true, aliases: ['Spring'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['java'], tags: ['backend', 'enterprise', 'microservices'] },
    { id: 'rails', name: 'Ruby on Rails', category: 'web-frameworks', certifiable: false, aliases: ['Rails'], marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 12, relatedSkillIds: ['ruby'], tags: ['backend', 'fullstack', 'web'] },
    { id: 'laravel', name: 'Laravel', category: 'web-frameworks', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['php'], tags: ['backend', 'fullstack', 'web'] },
    { id: 'dotnet', name: '.NET', category: 'web-frameworks', certifiable: true, aliases: ['ASP.NET', 'DotNet'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 17, relatedSkillIds: ['csharp'], tags: ['backend', 'enterprise', 'fullstack'] },
    { id: 'graphql', name: 'GraphQL', category: 'web-frameworks', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['rest-api'], tags: ['api', 'web', 'query'] },
    { id: 'rest-api', name: 'REST APIs', category: 'web-frameworks', certifiable: false, aliases: ['REST', 'RESTful'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['graphql'], tags: ['api', 'web', 'backend'] },
    { id: 'html-css', name: 'HTML/CSS', category: 'web-frameworks', certifiable: false, aliases: ['HTML', 'CSS'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 5, relatedSkillIds: ['tailwind'], tags: ['frontend', 'web', 'ui'] },
    { id: 'tailwind', name: 'Tailwind CSS', category: 'web-frameworks', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 8, relatedSkillIds: ['html-css'], tags: ['frontend', 'css', 'ui'] },
    { id: 'sass', name: 'Sass/SCSS', category: 'web-frameworks', certifiable: false, aliases: ['SCSS'], marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, relatedSkillIds: ['html-css'], tags: ['frontend', 'css'] },
    { id: 'state-management', name: 'State Management', category: 'web-frameworks', certifiable: false, aliases: ['Redux', 'MobX', 'Zustand', 'Frontend State'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['react', 'vue'], tags: ['frontend', 'architecture', 'state'] },

    // =========================================================================
    // MOBILE DEVELOPMENT
    // =========================================================================
    { id: 'react-native', name: 'React Native', category: 'mobile-development', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['react', 'javascript'], tags: ['mobile', 'cross-platform'] },
    { id: 'flutter', name: 'Flutter', category: 'mobile-development', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['mobile', 'cross-platform', 'dart'] },
    { id: 'ios-development', name: 'iOS Development', category: 'mobile-development', certifiable: true, aliases: ['iOS'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 20, relatedSkillIds: ['swift', 'swiftui'], tags: ['mobile', 'ios', 'apple'] },
    { id: 'android-development', name: 'Android Development', category: 'mobile-development', certifiable: true, aliases: ['Android'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['kotlin', 'java'], tags: ['mobile', 'android', 'google'] },
    { id: 'swiftui', name: 'SwiftUI', category: 'mobile-development', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['swift', 'ios-development'], tags: ['mobile', 'ios', 'ui'] },
    { id: 'mobile-ui', name: 'Mobile UI', category: 'mobile-development', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, tags: ['mobile', 'ui', 'design'] },
    { id: 'mobile-architecture', name: 'Mobile Architecture', category: 'mobile-development', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, tags: ['mobile', 'architecture'] },

    // =========================================================================
    // CLOUD & DEVOPS
    // =========================================================================
    { id: 'aws', name: 'AWS', category: 'cloud-devops', certifiable: true, aliases: ['Amazon Web Services'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 20, relatedSkillIds: ['cloud-architecture', 'serverless'], tags: ['cloud', 'infrastructure'] },
    { id: 'gcp', name: 'Google Cloud', category: 'cloud-devops', certifiable: true, aliases: ['GCP', 'Google Cloud Platform'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['cloud-architecture'], tags: ['cloud', 'infrastructure'] },
    { id: 'azure', name: 'Azure', category: 'cloud-devops', certifiable: true, aliases: ['Microsoft Azure'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['cloud-architecture'], tags: ['cloud', 'infrastructure', 'enterprise'] },
    { id: 'docker', name: 'Docker', category: 'cloud-devops', certifiable: true, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['kubernetes'], tags: ['containers', 'devops'] },
    { id: 'kubernetes', name: 'Kubernetes', category: 'cloud-devops', certifiable: true, aliases: ['K8s'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['docker'], tags: ['containers', 'orchestration', 'devops'] },
    { id: 'terraform', name: 'Terraform', category: 'cloud-devops', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['infrastructure-as-code'], tags: ['iac', 'devops', 'automation'] },
    { id: 'ansible', name: 'Ansible', category: 'cloud-devops', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['infrastructure-as-code'], tags: ['automation', 'devops', 'config'] },
    { id: 'ci-cd', name: 'CI/CD', category: 'cloud-devops', certifiable: false, aliases: ['Continuous Integration', 'Continuous Deployment'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['github-actions', 'jenkins'], tags: ['devops', 'automation'] },
    { id: 'github-actions', name: 'GitHub Actions', category: 'cloud-devops', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 10, relatedSkillIds: ['ci-cd'], tags: ['ci-cd', 'github', 'automation'] },
    { id: 'jenkins', name: 'Jenkins', category: 'cloud-devops', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 10, relatedSkillIds: ['ci-cd'], tags: ['ci-cd', 'automation'] },
    { id: 'linux', name: 'Linux', category: 'cloud-devops', certifiable: true, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['bash'], tags: ['os', 'server', 'devops'] },
    { id: 'git', name: 'Git', category: 'cloud-devops', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 5, tags: ['version-control', 'collaboration'] },
    { id: 'monitoring', name: 'Monitoring', category: 'cloud-devops', certifiable: false, aliases: ['Observability'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['observability'], tags: ['devops', 'sre'] },
    { id: 'cloud-architecture', name: 'Cloud Architecture', category: 'cloud-devops', certifiable: false, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 25, relatedSkillIds: ['aws', 'gcp', 'azure'], tags: ['architecture', 'cloud'] },
    { id: 'serverless', name: 'Serverless', category: 'cloud-devops', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['aws', 'cloud-architecture'], tags: ['cloud', 'architecture'] },
    { id: 'infrastructure-as-code', name: 'Infrastructure as Code', category: 'cloud-devops', certifiable: false, aliases: ['IaC'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['terraform', 'ansible'], tags: ['devops', 'automation'] },
    { id: 'networking', name: 'Networking', category: 'cloud-devops', certifiable: true, aliases: ['Network Fundamentals', 'TCP/IP'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['linux', 'cloud-architecture'], tags: ['infrastructure', 'sre', 'fundamentals'] },
    { id: 'scripting', name: 'Scripting', category: 'cloud-devops', certifiable: false, aliases: ['Shell Scripting', 'Automation Scripts'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['bash', 'python'], tags: ['automation', 'devops', 'sysadmin'] },
    { id: 'slos', name: 'SLOs', category: 'cloud-devops', certifiable: false, aliases: ['SLIs', 'Service Level Objectives', 'Reliability Metrics'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['monitoring', 'observability'], tags: ['sre', 'reliability', 'metrics'] },
    { id: 'observability', name: 'Observability', category: 'cloud-devops', certifiable: false, aliases: ['O11y'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['monitoring', 'slos'], tags: ['sre', 'devops', 'infrastructure'] },

    // =========================================================================
    // DATABASES
    // =========================================================================
    { id: 'postgresql', name: 'PostgreSQL', category: 'databases', certifiable: true, aliases: ['Postgres'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['sql', 'database-design'], tags: ['database', 'sql', 'relational'] },
    { id: 'mysql', name: 'MySQL', category: 'databases', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['sql'], tags: ['database', 'sql', 'relational'] },
    { id: 'mongodb', name: 'MongoDB', category: 'databases', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['nosql'], tags: ['database', 'nosql', 'document'] },
    { id: 'redis', name: 'Redis', category: 'databases', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['database', 'cache', 'nosql'] },
    { id: 'elasticsearch', name: 'Elasticsearch', category: 'databases', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, tags: ['database', 'search', 'analytics'] },
    { id: 'dynamodb', name: 'DynamoDB', category: 'databases', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['aws', 'nosql'], tags: ['database', 'nosql', 'aws'] },
    { id: 'cassandra', name: 'Cassandra', category: 'databases', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['nosql'], tags: ['database', 'nosql', 'distributed'] },
    { id: 'firestore', name: 'Firestore', category: 'databases', certifiable: false, marketDemand: 'medium', trendDirection: 'growing', avgSalaryImpact: 10, relatedSkillIds: ['gcp', 'nosql'], tags: ['database', 'nosql', 'firebase'] },
    { id: 'oracle', name: 'Oracle DB', category: 'databases', certifiable: true, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 18, relatedSkillIds: ['sql'], tags: ['database', 'sql', 'enterprise'] },
    { id: 'sql-server', name: 'SQL Server', category: 'databases', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['sql', 'azure'], tags: ['database', 'sql', 'microsoft'] },
    { id: 'neo4j', name: 'Neo4j', category: 'databases', certifiable: false, marketDemand: 'medium', trendDirection: 'growing', avgSalaryImpact: 15, tags: ['database', 'graph', 'nosql'] },
    { id: 'database-design', name: 'Database Design', category: 'databases', certifiable: false, aliases: ['Data Modeling'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['sql'], tags: ['database', 'architecture', 'design'] },
    { id: 'nosql', name: 'NoSQL', category: 'databases', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['mongodb', 'redis'], tags: ['database', 'distributed'] },
    { id: 'databases', name: 'Databases', category: 'databases', certifiable: true, aliases: ['Database Management', 'RDBMS'], marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['sql', 'postgresql', 'mysql', 'mongodb'], tags: ['database', 'backend', 'data'] },

    // =========================================================================
    // DATA ENGINEERING
    // =========================================================================
    { id: 'spark', name: 'Apache Spark', category: 'data-engineering', certifiable: true, aliases: ['Spark'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['scala', 'python'], tags: ['data', 'big-data', 'processing'] },
    { id: 'airflow', name: 'Apache Airflow', category: 'data-engineering', certifiable: false, aliases: ['Airflow'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['etl'], tags: ['data', 'orchestration', 'pipeline'] },
    { id: 'kafka', name: 'Apache Kafka', category: 'data-engineering', certifiable: true, aliases: ['Kafka'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 20, tags: ['data', 'streaming', 'messaging'] },
    { id: 'hadoop', name: 'Hadoop', category: 'data-engineering', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 15, tags: ['data', 'big-data', 'legacy'] },
    { id: 'etl', name: 'ETL', category: 'data-engineering', certifiable: false, aliases: ['Extract Transform Load'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['airflow'], tags: ['data', 'pipeline', 'integration'] },
    { id: 'data-warehousing', name: 'Data Warehousing', category: 'data-engineering', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['cloud-data'], tags: ['data', 'analytics', 'architecture'] },
    { id: 'data-architecture', name: 'Data Architecture', category: 'data-engineering', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 25, tags: ['data', 'architecture', 'design'] },
    { id: 'data-governance', name: 'Data Governance', category: 'data-engineering', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['data', 'compliance', 'quality'] },
    { id: 'data-modeling', name: 'Data Modeling', category: 'data-engineering', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['database-design'], tags: ['data', 'design', 'architecture'] },
    { id: 'cloud-data', name: 'Cloud Data Platforms', category: 'data-engineering', certifiable: false, aliases: ['BigQuery', 'Snowflake', 'Redshift'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 22, tags: ['data', 'cloud', 'analytics'] },
    { id: 'data-analysis', name: 'Data Analysis', category: 'data-engineering', certifiable: true, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['sql', 'python', 'statistics'], tags: ['data', 'analytics', 'insights'] },
    { id: 'data-visualization', name: 'Data Visualization', category: 'data-engineering', certifiable: false, aliases: ['Tableau', 'Power BI'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['data', 'analytics', 'visualization'] },
    { id: 'visualization', name: 'Visualization', category: 'data-engineering', certifiable: false, aliases: ['Charts', 'Graphs', 'Visual Analytics'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['data-visualization', 'data-analysis'], tags: ['data', 'analytics', 'visual'] },
    { id: 'statistics', name: 'Statistics', category: 'data-engineering', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['data-analysis', 'r'], tags: ['data', 'math', 'analytics'] },
    { id: 'ab-testing', name: 'A/B Testing', category: 'data-engineering', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['statistics'], tags: ['data', 'experimentation', 'product'] },

    // =========================================================================
    // MACHINE LEARNING & AI
    // =========================================================================
    { id: 'ml-fundamentals', name: 'Machine Learning', category: 'machine-learning', certifiable: true, aliases: ['ML', 'ML Fundamentals'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 25, relatedSkillIds: ['python', 'statistics'], tags: ['ml', 'ai', 'data-science'] },
    { id: 'deep-learning', name: 'Deep Learning', category: 'machine-learning', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 28, relatedSkillIds: ['tensorflow', 'pytorch'], tags: ['ml', 'ai', 'neural-networks'] },
    { id: 'tensorflow', name: 'TensorFlow', category: 'machine-learning', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['deep-learning', 'python'], tags: ['ml', 'framework', 'google'] },
    { id: 'pytorch', name: 'PyTorch', category: 'machine-learning', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['deep-learning', 'python'], tags: ['ml', 'framework', 'research'] },
    { id: 'scikit-learn', name: 'Scikit-learn', category: 'machine-learning', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['python', 'ml-fundamentals'], tags: ['ml', 'python', 'library'] },
    { id: 'nlp', name: 'NLP', category: 'machine-learning', certifiable: true, aliases: ['Natural Language Processing'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 28, relatedSkillIds: ['llm-engineering'], tags: ['ml', 'ai', 'text'] },
    { id: 'computer-vision', name: 'Computer Vision', category: 'machine-learning', certifiable: true, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 25, relatedSkillIds: ['deep-learning'], tags: ['ml', 'ai', 'image'] },
    { id: 'llm-engineering', name: 'LLM Engineering', category: 'machine-learning', certifiable: false, aliases: ['Large Language Models'], marketDemand: 'critical', trendDirection: 'emerging', avgSalaryImpact: 35, relatedSkillIds: ['nlp', 'python'], tags: ['ml', 'ai', 'genai'] },
    { id: 'mlops', name: 'MLOps', category: 'machine-learning', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['ml-fundamentals', 'ci-cd'], tags: ['ml', 'devops', 'deployment'] },
    { id: 'ml-architecture', name: 'ML Architecture', category: 'machine-learning', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 28, relatedSkillIds: ['ml-fundamentals', 'system-design'], tags: ['ml', 'architecture', 'design'] },

    // =========================================================================
    // SECURITY
    // =========================================================================
    { id: 'security', name: 'Security', category: 'security', certifiable: true, aliases: ['Cybersecurity Fundamentals', 'InfoSec'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['security-fundamentals', 'application-security'], tags: ['security', 'fundamentals'] },
    { id: 'security-fundamentals', name: 'Security Fundamentals', category: 'security', certifiable: true, aliases: ['Cybersecurity'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 20, tags: ['security', 'fundamentals'] },
    { id: 'appsec', name: 'AppSec', category: 'security', certifiable: true, aliases: ['Application Security', 'App Security'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['application-security'], tags: ['security', 'development'] },
    { id: 'application-security', name: 'Application Security', category: 'security', certifiable: true, aliases: ['AppSec'], marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 22, tags: ['security', 'development'] },
    { id: 'secops', name: 'SecOps', category: 'security', certifiable: false, aliases: ['Security Operations', 'Security Ops'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['security-operations', 'incident-response'], tags: ['security', 'operations'] },
    { id: 'cloud-security', name: 'Cloud Security', category: 'security', certifiable: true, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 25, relatedSkillIds: ['aws', 'gcp', 'azure'], tags: ['security', 'cloud'] },
    { id: 'network-security', name: 'Network Security', category: 'security', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 20, tags: ['security', 'network', 'infrastructure'] },
    { id: 'penetration-testing', name: 'Penetration Testing', category: 'security', certifiable: true, aliases: ['PenTest'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 25, tags: ['security', 'offensive'] },
    { id: 'threat-modeling', name: 'Threat Modeling', category: 'security', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['security', 'design'] },
    { id: 'security-architecture', name: 'Security Architecture', category: 'security', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 28, tags: ['security', 'architecture'] },
    { id: 'incident-response', name: 'Incident Response', category: 'security', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, tags: ['security', 'operations'] },
    { id: 'compliance', name: 'Compliance', category: 'security', certifiable: false, aliases: ['GDPR', 'SOC2', 'HIPAA'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, tags: ['security', 'governance'] },
    { id: 'risk-management', name: 'Risk Management', category: 'security', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, tags: ['security', 'governance'] },
    { id: 'security-operations', name: 'Security Operations', category: 'security', certifiable: false, aliases: ['SecOps'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['security', 'operations'] },
    { id: 'security-tools', name: 'Security Tools', category: 'security', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['security', 'tools'] },

    // =========================================================================
    // TESTING & QA
    // =========================================================================
    { id: 'testing', name: 'Testing', category: 'testing-qa', certifiable: false, aliases: ['Software Testing'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, tags: ['testing', 'quality'] },
    { id: 'test-automation', name: 'Test Automation', category: 'testing-qa', certifiable: true, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['selenium', 'cypress', 'playwright'], tags: ['testing', 'automation'] },
    { id: 'unit-testing', name: 'Unit Testing', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['jest'], tags: ['testing', 'fundamentals'] },
    { id: 'integration-testing', name: 'Integration Testing', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['testing', 'integration'] },
    { id: 'e2e-testing', name: 'E2E Testing', category: 'testing-qa', certifiable: false, aliases: ['End-to-End Testing'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['cypress', 'playwright'], tags: ['testing', 'automation'] },
    { id: 'selenium', name: 'Selenium', category: 'testing-qa', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 10, tags: ['testing', 'automation', 'browser'] },
    { id: 'cypress', name: 'Cypress', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, tags: ['testing', 'automation', 'javascript'] },
    { id: 'playwright', name: 'Playwright', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'emerging', avgSalaryImpact: 12, tags: ['testing', 'automation', 'browser'] },
    { id: 'jest', name: 'Jest', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['javascript', 'react'], tags: ['testing', 'javascript', 'unit'] },
    { id: 'performance-testing', name: 'Performance Testing', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, tags: ['testing', 'performance'] },
    { id: 'manual-testing', name: 'Manual Testing', category: 'testing-qa', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 5, tags: ['testing', 'manual'] },
    { id: 'test-architecture', name: 'Test Architecture', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['testing', 'architecture'] },
    { id: 'quality-strategy', name: 'Quality Strategy', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, tags: ['testing', 'strategy', 'leadership'] },
    { id: 'tdd', name: 'TDD', category: 'testing-qa', certifiable: false, aliases: ['Test-Driven Development'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['testing', 'development', 'practice'] },
    { id: 'api-testing', name: 'API Testing', category: 'testing-qa', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, tags: ['testing', 'api', 'automation'] },
    { id: 'bug-reporting', name: 'Bug Reporting', category: 'testing-qa', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, tags: ['testing', 'communication'] },
    { id: 'test-cases', name: 'Test Cases', category: 'testing-qa', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, tags: ['testing', 'documentation'] },

    // =========================================================================
    // ARCHITECTURE & SYSTEM DESIGN
    // =========================================================================
    { id: 'system-design', name: 'System Design', category: 'architecture', certifiable: true, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 25, relatedSkillIds: ['distributed-systems', 'scalability'], tags: ['architecture', 'design', 'senior'] },
    { id: 'microservices', name: 'Microservices', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['docker', 'kubernetes'], tags: ['architecture', 'distributed'] },
    { id: 'distributed-systems', name: 'Distributed Systems', category: 'architecture', certifiable: true, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 25, relatedSkillIds: ['system-design'], tags: ['architecture', 'scalability'] },
    { id: 'design-patterns', name: 'Design Patterns', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['architecture', 'fundamentals'] },
    { id: 'api-design', name: 'API Design', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['rest-api', 'graphql'], tags: ['architecture', 'api'] },
    { id: 'scalability', name: 'Scalability', category: 'architecture', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['system-design'], tags: ['architecture', 'performance'] },
    { id: 'reliability', name: 'Reliability', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 20, relatedSkillIds: ['slos-slis'], tags: ['architecture', 'sre'] },
    { id: 'performance', name: 'Performance', category: 'architecture', certifiable: false, aliases: ['Performance Optimization'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, tags: ['architecture', 'optimization'] },
    { id: 'architecture', name: 'Software Architecture', category: 'architecture', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 25, tags: ['architecture', 'design', 'senior'] },
    { id: 'platform-architecture', name: 'Platform Architecture', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 28, tags: ['architecture', 'platform'] },
    { id: 'slos-slis', name: 'SLOs/SLIs', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['reliability'], tags: ['sre', 'operations'] },
    { id: 'chaos-engineering', name: 'Chaos Engineering', category: 'architecture', certifiable: false, marketDemand: 'medium', trendDirection: 'growing', avgSalaryImpact: 18, tags: ['sre', 'reliability'] },
    { id: 'observability', name: 'Observability', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['monitoring'], tags: ['sre', 'operations'] },
    { id: 'automation', name: 'Automation', category: 'architecture', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, tags: ['devops', 'efficiency'] },

    // =========================================================================
    // DESIGN & UX
    // =========================================================================
    { id: 'ux-design', name: 'UX Design', category: 'design-ux', certifiable: true, aliases: ['User Experience'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['ui-design', 'user-research'], tags: ['design', 'product'] },
    { id: 'ui-design', name: 'UI Design', category: 'design-ux', certifiable: true, aliases: ['User Interface'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['ux-design', 'figma'], tags: ['design', 'visual'] },
    { id: 'product-design', name: 'Product Design', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['ux-design', 'ui-design'], tags: ['design', 'product', 'strategy'] },
    { id: 'figma', name: 'Figma', category: 'design-ux', certifiable: true, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 10, relatedSkillIds: ['ui-design'], tags: ['design', 'tool', 'collaboration'] },
    { id: 'sketch', name: 'Sketch', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 5, tags: ['design', 'tool', 'mac'] },
    { id: 'adobe-xd', name: 'Adobe XD', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'declining', avgSalaryImpact: 5, tags: ['design', 'tool', 'adobe'] },
    { id: 'user-research', name: 'User Research', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['ux-design', 'usability-testing'], tags: ['research', 'ux', 'qualitative'] },
    { id: 'usability-testing', name: 'Usability Testing', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['user-research'], tags: ['testing', 'ux', 'research'] },
    { id: 'wireframing', name: 'Wireframing', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, relatedSkillIds: ['prototyping'], tags: ['design', 'ux', 'planning'] },
    { id: 'prototyping', name: 'Prototyping', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['figma', 'wireframing'], tags: ['design', 'ux', 'validation'] },
    { id: 'design-systems', name: 'Design Systems', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['ui-design', 'figma'], tags: ['design', 'architecture', 'scalability'] },
    { id: 'design-strategy', name: 'Design Strategy', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 20, relatedSkillIds: ['product-design'], tags: ['design', 'strategy', 'leadership'] },
    { id: 'visual-design', name: 'Visual Design', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['ui-design'], tags: ['design', 'creative', 'visual'] },
    { id: 'typography', name: 'Typography', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, tags: ['design', 'visual', 'fundamentals'] },
    { id: 'color-theory', name: 'Color Theory', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 5, tags: ['design', 'visual', 'fundamentals'] },
    { id: 'brand-design', name: 'Brand Design', category: 'design-ux', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 12, tags: ['design', 'marketing', 'creative'] },
    { id: 'information-architecture', name: 'Information Architecture', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['ux-design'], tags: ['ux', 'architecture', 'structure'] },
    { id: 'accessibility', name: 'Accessibility', category: 'design-ux', certifiable: false, aliases: ['a11y'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['ux-design'], tags: ['ux', 'compliance', 'inclusive'] },
    { id: 'responsive-design', name: 'Responsive Design', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['css', 'ui-design'], tags: ['frontend', 'mobile', 'design'] },
    { id: 'interaction-design', name: 'Interaction Design', category: 'design-ux', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['ux-design', 'prototyping'], tags: ['ux', 'animation', 'motion'] },

    // =========================================================================
    // PRODUCT MANAGEMENT
    // =========================================================================
    { id: 'product-strategy', name: 'Product Strategy', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 22, relatedSkillIds: ['roadmapping', 'market-analysis'], tags: ['product', 'strategy', 'leadership'] },
    { id: 'roadmapping', name: 'Roadmapping', category: 'product-management', certifiable: false, aliases: ['Roadmap Planning'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['product-strategy', 'prioritization'], tags: ['product', 'planning', 'strategy'] },
    { id: 'product-analytics', name: 'Product Analytics', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['data-analysis'], tags: ['product', 'data', 'analytics'] },
    { id: 'product-thinking', name: 'Product Thinking', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, tags: ['product', 'strategy', 'mindset'] },
    { id: 'market-analysis', name: 'Market Analysis', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['competitive-analysis'], tags: ['product', 'research', 'strategy'] },
    { id: 'competitive-analysis', name: 'Competitive Analysis', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['market-analysis'], tags: ['product', 'research', 'strategy'] },
    { id: 'agile', name: 'Agile', category: 'product-management', certifiable: true, aliases: ['Scrum', 'Kanban'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['project-management'], tags: ['methodology', 'process', 'team'] },
    { id: 'stakeholder-management', name: 'Stakeholder Management', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['communication'], tags: ['product', 'communication', 'leadership'] },
    { id: 'requirements-gathering', name: 'Requirements Gathering', category: 'product-management', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['stakeholder-management'], tags: ['product', 'analysis', 'discovery'] },
    { id: 'prioritization', name: 'Prioritization', category: 'product-management', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['roadmapping', 'product-strategy'], tags: ['product', 'decision-making', 'strategy'] },

    // =========================================================================
    // LEADERSHIP & MANAGEMENT
    // =========================================================================
    { id: 'leadership', name: 'Leadership', category: 'leadership', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 25, relatedSkillIds: ['people-management', 'decision-making'], tags: ['soft-skills', 'management', 'senior'] },
    { id: 'people-management', name: 'People Management', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['leadership', 'mentoring'], tags: ['management', 'hr', 'team'] },
    { id: 'mentoring', name: 'Mentoring', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['leadership'], tags: ['development', 'teaching', 'soft-skills'] },
    { id: 'team-building', name: 'Team Building', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['leadership', 'hiring'], tags: ['management', 'culture', 'team'] },
    { id: 'project-management', name: 'Project Management', category: 'leadership', certifiable: true, aliases: ['PM'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['agile'], tags: ['management', 'process', 'delivery'] },
    { id: 'org-design', name: 'Org Design', category: 'leadership', certifiable: false, aliases: ['Organizational Design'], marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 25, relatedSkillIds: ['leadership'], tags: ['management', 'strategy', 'executive'] },
    { id: 'hiring', name: 'Hiring', category: 'leadership', certifiable: false, aliases: ['Recruiting'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['team-building'], tags: ['management', 'hr', 'talent'] },
    { id: 'performance-reviews', name: 'Performance Reviews', category: 'leadership', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['people-management'], tags: ['management', 'hr', 'feedback'] },
    { id: 'conflict-resolution', name: 'Conflict Resolution', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 12, relatedSkillIds: ['communication'], tags: ['soft-skills', 'management', 'team'] },
    { id: 'executive-presence', name: 'Executive Presence', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 25, relatedSkillIds: ['leadership', 'presentation'], tags: ['soft-skills', 'executive', 'senior'] },
    { id: 'decision-making', name: 'Decision Making', category: 'leadership', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['leadership', 'critical-thinking'], tags: ['soft-skills', 'strategy', 'management'] },

    // =========================================================================
    // COMMUNICATION
    // =========================================================================
    { id: 'communication', name: 'Communication', category: 'communication', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['presentation', 'collaboration'], tags: ['soft-skills', 'fundamentals'] },
    { id: 'presentation', name: 'Presentation', category: 'communication', certifiable: false, aliases: ['Public Speaking'], marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['communication'], tags: ['soft-skills', 'public-speaking'] },
    { id: 'technical-writing', name: 'Technical Writing', category: 'communication', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['documentation'], tags: ['writing', 'documentation', 'technical'] },
    { id: 'documentation', name: 'Documentation', category: 'communication', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 8, relatedSkillIds: ['technical-writing'], tags: ['writing', 'knowledge-sharing'] },
    { id: 'collaboration', name: 'Collaboration', category: 'communication', certifiable: false, marketDemand: 'critical', trendDirection: 'growing', avgSalaryImpact: 12, relatedSkillIds: ['communication', 'cross-functional'], tags: ['soft-skills', 'teamwork'] },
    { id: 'negotiation', name: 'Negotiation', category: 'communication', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 18, relatedSkillIds: ['communication'], tags: ['soft-skills', 'business', 'sales'] },
    { id: 'cross-functional', name: 'Cross-functional Collaboration', category: 'communication', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 15, relatedSkillIds: ['collaboration', 'stakeholder-management'], tags: ['soft-skills', 'teamwork', 'coordination'] },

    // =========================================================================
    // BUSINESS & STRATEGY
    // =========================================================================
    { id: 'business-acumen', name: 'Business Acumen', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 20, relatedSkillIds: ['strategic-thinking'], tags: ['business', 'strategy', 'senior'] },
    { id: 'strategic-thinking', name: 'Strategic Thinking', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 22, relatedSkillIds: ['business-acumen', 'decision-making'], tags: ['strategy', 'leadership', 'senior'] },
    { id: 'problem-solving', name: 'Problem Solving', category: 'business', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['critical-thinking', 'analytical-skills'], tags: ['fundamentals', 'soft-skills'] },
    { id: 'critical-thinking', name: 'Critical Thinking', category: 'business', certifiable: false, marketDemand: 'critical', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['problem-solving', 'analytical-skills'], tags: ['fundamentals', 'soft-skills'] },
    { id: 'analytical-skills', name: 'Analytical Skills', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['data-analysis', 'critical-thinking'], tags: ['fundamentals', 'data'] },
    { id: 'process-improvement', name: 'Process Improvement', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'stable', avgSalaryImpact: 15, relatedSkillIds: ['automation'], tags: ['operations', 'efficiency', 'optimization'] },
    { id: 'cost-optimization', name: 'Cost Optimization', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['process-improvement'], tags: ['operations', 'efficiency', 'finops'] },
    { id: 'research', name: 'Research', category: 'business', certifiable: false, marketDemand: 'medium', trendDirection: 'stable', avgSalaryImpact: 10, relatedSkillIds: ['analytical-skills'], tags: ['analysis', 'discovery'] },
    { id: 'innovation', name: 'Innovation', category: 'business', certifiable: false, marketDemand: 'high', trendDirection: 'growing', avgSalaryImpact: 18, relatedSkillIds: ['strategic-thinking', 'problem-solving'], tags: ['creativity', 'strategy', 'leadership'] },
    { id: 'developer-experience', name: 'Developer Experience', category: 'business', certifiable: false, aliases: ['DX'], marketDemand: 'high', trendDirection: 'emerging', avgSalaryImpact: 18, relatedSkillIds: ['documentation', 'automation'], tags: ['platform', 'productivity', 'tooling'] }
];

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

/**
 * Get all skills
 */
export const getAllSkills = (): Skill[] => MASTER_SKILLS;

/**
 * Get skill by ID
 */
export const getSkillById = (id: string): Skill | undefined => {
    return MASTER_SKILLS.find(s => s.id === id);
};

/**
 * Get skill by name (case-insensitive)
 */
export const getSkillByName = (name: string): Skill | undefined => {
    const normalized = name.toLowerCase().trim();
    return MASTER_SKILLS.find(s =>
        s.name.toLowerCase() === normalized ||
        s.aliases?.some(a => a.toLowerCase() === normalized)
    );
};

/**
 * Search skills by query (searches name and aliases)
 */
export const searchSkills = (query: string): Skill[] => {
    const normalized = query.toLowerCase().trim();
    if (!normalized) return MASTER_SKILLS;

    return MASTER_SKILLS.filter(s =>
        s.name.toLowerCase().includes(normalized) ||
        s.aliases?.some(a => a.toLowerCase().includes(normalized))
    );
};

/**
 * Get skills by category
 */
export const getSkillsByCategory = (category: SkillCategory): Skill[] => {
    return MASTER_SKILLS.filter(s => s.category === category);
};

/**
 * Get certifiable skills only
 */
export const getCertifiableSkills = (): Skill[] => {
    return MASTER_SKILLS.filter(s => s.certifiable);
};

/**
 * Get skill names for autocomplete (sorted alphabetically)
 */
export const getSkillNames = (): string[] => {
    return MASTER_SKILLS.map(s => s.name).sort();
};

/**
 * Get skills grouped by category
 */
export const getSkillsGroupedByCategory = (): Map<SkillCategory, Skill[]> => {
    const grouped = new Map<SkillCategory, Skill[]>();
    for (const skill of MASTER_SKILLS) {
        const existing = grouped.get(skill.category) || [];
        existing.push(skill);
        grouped.set(skill.category, existing);
    }
    return grouped;
};

/**
 * Get category metadata by ID
 */
export const getCategoryById = (id: SkillCategory): SkillCategoryMeta | undefined => {
    return SKILL_CATEGORIES.find(c => c.id === id);
};

/**
 * Normalize skill name to ID
 */
export const normalizeSkillToId = (name: string): string => {
    const skill = getSkillByName(name);
    return skill?.id || name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
};

/**
 * Match a skill name to the closest master skill
 * Uses word-boundary matching to avoid false positives (e.g., "C" matching "Executive")
 */
export const matchSkillName = (name: string): Skill | null => {
    // Exact match first
    const exact = getSkillByName(name);
    if (exact) return exact;

    const normalized = name.toLowerCase().trim();

    // Helper: Check if a term matches as a complete word in a string
    // This prevents "C" from matching "Executive" but allows "React" to match "React Native"
    const matchesAsWord = (text: string, term: string): boolean => {
        if (term.length < 2) {
            // For single-char terms (like "C", "R"), require exact word match
            const words = text.split(/\s+/);
            return words.some(word => word === term);
        }
        // For longer terms, allow partial word matches but with word boundary
        // E.g., "javascript" should match "JavaScript", "React" should match "React Native"
        const regex = new RegExp(`\\b${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`, 'i');
        return regex.test(text);
    };

    // Try to find a skill where:
    // 1. The master skill name matches as a word in the user's skill name, OR
    // 2. The user's skill name matches as a word in the master skill name
    const partial = MASTER_SKILLS.find(s => {
        const skillName = s.name.toLowerCase();

        // Check if master skill name appears as a word in user's input
        if (matchesAsWord(normalized, skillName)) return true;

        // Check if user's input appears as a word in master skill name (for partial matches)
        if (normalized.length >= 3 && matchesAsWord(skillName, normalized)) return true;

        // Check aliases
        return s.aliases?.some(a => {
            const alias = a.toLowerCase();
            return matchesAsWord(normalized, alias) ||
                   (normalized.length >= 3 && matchesAsWord(alias, normalized));
        });
    });

    return partial || null;
};

// ============================================================================
// EXPORTS FOR DROPDOWNS
// ============================================================================

/**
 * Get skills formatted for dropdown/autocomplete
 */
export const getSkillsForDropdown = (): Array<{ id: string; name: string; category: string }> => {
    return MASTER_SKILLS.map(s => ({
        id: s.id,
        name: s.name,
        category: getCategoryById(s.category)?.name || s.category
    })).sort((a, b) => a.name.localeCompare(b.name));
};

// Export count for verification
export const TOTAL_SKILLS_COUNT = MASTER_SKILLS.length;
