import { addDays, subWeeks } from 'date-fns';

import type {
  DemandPoint,
  MarketDemandResponse,
  RoleTemplateResponse,
  SkillAdjacencyEdge,
  SkillExpandResponse
} from './types';

const SKILL_LABELS: Record<string, string> = {
  javascript: 'JavaScript',
  python: 'Python',
  react: 'React',
  nodejs: 'Node.js',
  aws: 'Amazon Web Services',
  sql: 'SQL',
  typescript: 'TypeScript',
  docker: 'Docker',
  kubernetes: 'Kubernetes',
  dataeng: 'Data Engineering'
};

const SEED_SKILL_EDGES: Record<string, SkillAdjacencyEdge[]> = {
  javascript: [
    { skillId: 'typescript', label: SKILL_LABELS.typescript, score: 0.87, support: 128, recencyDays: 14, sources: ['job_postings'] },
    { skillId: 'react', label: SKILL_LABELS.react, score: 0.83, support: 142, recencyDays: 10, sources: ['job_postings', 'eco_templates'] },
    { skillId: 'nodejs', label: SKILL_LABELS.nodejs, score: 0.74, support: 96, recencyDays: 21, sources: ['job_postings'] },
    { skillId: 'docker', label: SKILL_LABELS.docker, score: 0.52, support: 88, recencyDays: 28, sources: ['job_postings'] },
    { skillId: 'aws', label: SKILL_LABELS.aws, score: 0.48, support: 77, recencyDays: 35, sources: ['job_postings', 'profiles'] }
  ],
  python: [
    { skillId: 'sql', label: SKILL_LABELS.sql, score: 0.79, support: 154, recencyDays: 12, sources: ['job_postings', 'profiles'] },
    { skillId: 'dataeng', label: 'Data Engineering', score: 0.68, support: 102, recencyDays: 18, sources: ['job_postings'] },
    { skillId: 'docker', label: SKILL_LABELS.docker, score: 0.54, support: 86, recencyDays: 24, sources: ['job_postings'] },
    { skillId: 'aws', label: SKILL_LABELS.aws, score: 0.51, support: 79, recencyDays: 20, sources: ['job_postings'] }
  ],
  react: [
    { skillId: 'javascript', label: SKILL_LABELS.javascript, score: 0.91, support: 210, recencyDays: 7, sources: ['job_postings'] },
    { skillId: 'typescript', label: SKILL_LABELS.typescript, score: 0.82, support: 124, recencyDays: 11, sources: ['job_postings'] },
    { skillId: 'nodejs', label: SKILL_LABELS.nodejs, score: 0.59, support: 94, recencyDays: 22, sources: ['job_postings'] }
  ],
  nodejs: [
    { skillId: 'javascript', label: SKILL_LABELS.javascript, score: 0.78, support: 132, recencyDays: 9, sources: ['job_postings'] },
    { skillId: 'typescript', label: SKILL_LABELS.typescript, score: 0.63, support: 86, recencyDays: 18, sources: ['job_postings'] },
    { skillId: 'docker', label: SKILL_LABELS.docker, score: 0.55, support: 73, recencyDays: 26, sources: ['job_postings'] }
  ]
};

interface BuildSkillExpansionOptions {
  skillId: string;
  topK: number;
  tenantId: string;
  filters?: SkillExpandResponse['meta']['filters'];
}

export function buildSeedSkillExpansion(options: BuildSkillExpansionOptions): SkillExpandResponse {
  const { skillId, topK, tenantId, filters } = options;
  const adjacent = (SEED_SKILL_EDGES[skillId] ?? [])
    .sort((a, b) => b.score - a.score)
    .slice(0, topK);

  return {
    seedSkill: {
      skillId,
      label: SKILL_LABELS[skillId] ?? skillId
    },
    adjacent,
    cacheHit: false,
    generatedAt: new Date().toISOString(),
    meta: {
      tenantId,
      filters,
      algorithm: 'pmi-seed'
    }
  } satisfies SkillExpandResponse;
}

interface SeedTemplateOptions {
  ecoId: string;
  locale: string;
}

const ROLE_TEMPLATE_DATA: Record<string, RoleTemplateResponse> = {
  'frontend-developer': {
    ecoId: 'frontend-developer',
    locale: 'pt-BR',
    title: 'Desenvolvedor Frontend',
    version: '2024.1',
    summary: 'Responsável por desenvolver interfaces ricas em React e JavaScript para produtos digitais.',
    requiredSkills: [
      { skillId: 'javascript', label: 'JavaScript', importance: 0.95, source: 'required' },
      { skillId: 'react', label: 'React', importance: 0.92, source: 'required' },
      { skillId: 'html', label: 'HTML5', importance: 0.72, source: 'required' }
    ],
    preferredSkills: [
      { skillId: 'nodejs', label: 'Node.js', importance: 0.55, source: 'preferred' },
      { skillId: 'typescript', label: 'TypeScript', importance: 0.67, source: 'preferred' }
    ],
    yearsExperienceMin: 2,
    yearsExperienceMax: 5,
    cacheHit: false,
    generatedAt: new Date().toISOString()
  },
  'backend-developer': {
    ecoId: 'backend-developer',
    locale: 'pt-BR',
    title: 'Desenvolvedor Backend',
    version: '2024.1',
    summary: 'Constrói e mantém APIs escaláveis utilizando Node.js e Python com foco em performance e segurança.',
    requiredSkills: [
      { skillId: 'nodejs', label: 'Node.js', importance: 0.9, source: 'required' },
      { skillId: 'python', label: 'Python', importance: 0.78, source: 'required' },
      { skillId: 'sql', label: 'SQL', importance: 0.75, source: 'required' }
    ],
    preferredSkills: [
      { skillId: 'docker', label: 'Docker', importance: 0.6, source: 'preferred' },
      { skillId: 'aws', label: 'AWS', importance: 0.58, source: 'preferred' }
    ],
    yearsExperienceMin: 3,
    yearsExperienceMax: 6,
    cacheHit: false,
    generatedAt: new Date().toISOString()
  }
};

export function buildSeedRoleTemplate({ ecoId, locale }: SeedTemplateOptions): RoleTemplateResponse | null {
  const template = ROLE_TEMPLATE_DATA[ecoId];
  if (!template) {
    return null;
  }

  if (template.locale === locale) {
    return {
      ...template,
      generatedAt: new Date().toISOString(),
      cacheHit: false
    };
  }

  return {
    ...template,
    locale,
    generatedAt: new Date().toISOString(),
    cacheHit: false
  } satisfies RoleTemplateResponse;
}

interface SeedDemandOptions {
  skillId: string;
  region: string;
  windowWeeks: number;
  industry?: string;
}

const DEMAND_TEMPLATES: Record<string, number[]> = {
  javascript: [120, 132, 140, 145, 150, 162, 168, 175, 181, 190, 205, 212],
  python: [98, 100, 105, 111, 118, 125, 129, 132, 138, 144, 151, 159],
  react: [110, 116, 124, 130, 137, 140, 145, 149, 158, 162, 170, 177]
};

export function buildSeedMarketDemand(
  options: SeedDemandOptions
): MarketDemandResponse | null {
  const { skillId, region, windowWeeks, industry } = options;
  const series = DEMAND_TEMPLATES[skillId];
  if (!series) {
    return null;
  }

  const now = new Date();
  const points: DemandPoint[] = [];
  for (let i = 0; i < Math.min(windowWeeks, series.length); i += 1) {
    const value = series[series.length - 1 - i];
    const weekStartDate = subWeeks(now, i);
    const normalizedStart = addDays(weekStartDate, -weekStartDate.getDay());
    points.unshift({
      weekStart: normalizedStart.toISOString().slice(0, 10),
      postings: value,
      ema: value * 0.92,
      zScore: (value - series[0]) / (series[series.length - 1] - series[0] || 1)
    });
  }

  const latestEma = points.length > 0 ? points[points.length - 1].ema : 0;
  const trend = latestEma > points[0]?.ema ? 'rising' : latestEma === points[0]?.ema ? 'steady' : 'declining';

  const payload: MarketDemandResponse = {
    skillId,
    region,
    industry,
    points,
    latestEma,
    cacheHit: false,
    generatedAt: new Date().toISOString(),
    trend: trend ?? 'steady'
  } satisfies MarketDemandResponse;

  return payload;
}
