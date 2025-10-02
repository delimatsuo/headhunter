import Fastify from 'fastify';
import { randomUUID } from 'node:crypto';

const port = Number.parseInt(process.env.MOCK_TOGETHER_PORT ?? '7500', 10);
const fastify = Fastify({ logger: true });

fastify.get('/health', async () => ({ status: 'ok' }));

fastify.post('/chat/completions', async (request, reply) => {
  const body = request.body ?? {};
  const messages = Array.isArray(body.messages) ? body.messages : [];

  const userMessage = messages.find((message) => message?.role === 'user');
  const userContent = typeof userMessage?.content === 'string' ? userMessage.content : '';
  const isRerank = userContent.includes('Candidates (return up to');

  let content;

  if (isRerank) {
    const candidateIds = new Set();
    const regex = /id=([A-Za-z0-9_-]+)/g;
    let match;
    while ((match = regex.exec(userContent)) !== null) {
      candidateIds.add(match[1]);
    }

    const ids = Array.from(candidateIds);
    if (ids.length === 0) {
      request.log.warn('Mock Together rerank did not find candidate IDs; defaulting to placeholder.');
      ids.push('fallback-1');
    }

    const scored = ids.map((id, index) => ({
      id,
      score: Number((1 - index * 0.1).toFixed(4))
    }));

    content = JSON.stringify({ results: scored });
  } else {
    const nameMatch = userContent.match(/\*\*Candidate Name:\*\*\s*(.*)/);
    const candidateName = nameMatch ? nameMatch[1].trim() : 'Candidato Anônimo';

    const enriched = {
      resume_analysis: {
        career_trajectory: {
          current_level: 'Senior',
          progression_speed: 'Fast',
          trajectory_type: 'Individual Contributor',
          years_experience: 8,
          career_changes: 2,
          domain_expertise: ['engenharia de software', 'cloud']
        },
        technical_skills: ['python', 'typescript', 'devops'],
        soft_skills: ['liderança', 'colaboração', 'comunicação'],
        leadership_scope: {
          has_leadership: true,
          team_size: 6,
          leadership_level: 'Team Lead',
          leadership_style: ['servant leadership', 'mentoria']
        },
        company_pedigree: {
          tier_level: 'Tier2',
          company_types: ['Startup', 'Enterprise'],
          recent_companies: ['InovaTech', 'CloudScale'],
          brand_recognition: 'Medium'
        },
        education: {
          highest_degree: 'BS',
          institutions: ['Universidade Federal'],
          fields_of_study: ['Engenharia da Computação']
        }
      },
      recruiter_insights: {
        sentiment: 'positive',
        strengths: ['Alta senioridade técnica', 'Excelente comunicação'],
        concerns: ['Disponibilidade para mudança internacional'],
        red_flags: [],
        cultural_fit: {
          cultural_alignment: 'excellent',
          work_style: ['colaborativo', 'hands-on'],
          values_alignment: ['aprendizado contínuo', 'impacto no usuário']
        },
        recommendation: 'hire',
        key_themes: ['liderança técnica', 'escala em cloud']
      },
      overall_score: 0.86,
      candidate_name: candidateName
    };

    content = JSON.stringify(enriched);
  }

  const payload = {
    id: `mock-${randomUUID()}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    choices: [
      {
        index: 0,
        finish_reason: 'stop',
        message: {
          role: 'assistant',
          content
        }
      }
    ],
    usage: {
      prompt_tokens: 512,
      completion_tokens: 64,
      total_tokens: 576
    }
  };

  reply.code(200).send(payload);
});

const start = async () => {
  try {
    await fastify.listen({ host: '0.0.0.0', port });
    fastify.log.info({ port }, 'Mock Together server listening');
  } catch (error) {
    fastify.log.error(error, 'Unable to start mock-together server');
    process.exit(1);
  }
};

start();
