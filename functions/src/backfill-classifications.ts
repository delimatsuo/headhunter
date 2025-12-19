/**
 * Backfill Searchable Classifications - v2
 * 
 * Updated to parse original_data.experience field which contains actual job titles.
 * Format: "- YYYY/MM - YYYY/MM\nCompany : Role\n\n"
 */

import * as admin from 'firebase-admin';
import { onRequest } from 'firebase-functions/v2/https';

const firestore = admin.firestore();

/**
 * Extract role from experience string
 * Format: "- YYYY/MM - YYYY/MM\nCompany : Role"
 */
function extractRoleFromExperience(experience: string): { role: string; company: string }[] {
    if (!experience) return [];

    const entries: { role: string; company: string }[] = [];
    const lines = experience.split('\n').filter(l => l.trim());

    let inEntry = false;
    for (const line of lines) {
        const trimmed = line.trim();

        // Date line starts an entry
        if (trimmed.startsWith('-') && /\d{4}/.test(trimmed)) {
            inEntry = true;
            continue;
        }

        // After date line, look for "Company : Role"
        if (inEntry && trimmed.includes(':')) {
            const parts = trimmed.split(':');
            if (parts.length >= 2) {
                entries.push({
                    company: parts[0].trim(),
                    role: parts.slice(1).join(':').trim()
                });
            }
            inEntry = false;
        }
    }

    return entries;
}

/**
 * Classify job function from text
 */
function classifyFunction(text: string): string {
    const t = text.toLowerCase();

    // Product function - higher priority
    if (t.includes('product') || t.includes('cpo') || t.includes('produto') ||
        /\bpm\b/.test(t) || t.includes('product manager') || t.includes('product owner')) {
        return 'product';
    }

    // Engineering function
    if (t.includes('engineer') || t.includes('developer') || t.includes('software') ||
        t.includes('cto') || t.includes('devops') || t.includes('frontend') ||
        t.includes('backend') || t.includes('full stack') || t.includes('fullstack') ||
        t.includes('sre') || t.includes('infrastructure') || t.includes('platform') ||
        t.includes('arquiteto') || t.includes('desenvolvedor') || t.includes('engenheiro') ||
        t.includes('programador') || t.includes('tech lead') || t.includes('technical lead')) {
        return 'engineering';
    }

    // Data function
    if (t.includes('data') || t.includes('analytics') || t.includes('scientist') ||
        t.includes('machine learning') || t.includes('ml ') || t.includes(' ml') ||
        t.includes('dados') || t.includes('cientista') || t.includes('bi ') ||
        t.includes('business intelligence')) {
        return 'data';
    }

    // Design function
    if (t.includes('design') || t.includes('ux') || t.includes('ui ') ||
        t.includes(' ui') || t.includes('creative') || t.includes('visual')) {
        return 'design';
    }

    // Sales function
    if (t.includes('sales') || t.includes('vendas') || t.includes('account') ||
        t.includes('revenue') || t.includes('business development') ||
        t.includes('executivo de contas') || t.includes('comercial')) {
        return 'sales';
    }

    // Marketing function
    if (t.includes('marketing') || t.includes('growth') || t.includes('brand') ||
        t.includes('content') || t.includes('social media') || t.includes('acquisition') ||
        t.includes('performance') || t.includes('digital marketing')) {
        return 'marketing';
    }

    // HR function
    if (t.includes(' hr ') || t.includes('people') || t.includes('talent') ||
        t.includes('recruit') || t.includes('human resources') || t.includes(' rh ') ||
        t.includes('recursos humanos') || t.includes('cultura') || t.includes('gente')) {
        return 'hr';
    }

    // Finance function
    if (t.includes('finance') || t.includes('cfo') || t.includes('accounting') ||
        t.includes('financeiro') || t.includes('controller') || t.includes('treasury') ||
        t.includes('contabil') || t.includes('fiscal')) {
        return 'finance';
    }

    // Operations function
    if (t.includes('operations') || t.includes('coo') || t.includes('logistics') ||
        t.includes('operações') || t.includes('supply chain') || t.includes('customer success') ||
        t.includes('customer support') || t.includes('cs ')) {
        return 'operations';
    }

    return 'general';
}

/**
 * Classify seniority level from text
 */
function classifyLevel(text: string): string {
    const t = text.toLowerCase();

    // C-Level
    if (t.includes('ceo') || t.includes('cto') || t.includes('cpo') || t.includes('cfo') ||
        t.includes('coo') || t.includes('cmo') || t.includes('cro') || t.includes('chief') ||
        t.includes('c-level') || t.includes('presidente') || t.includes('sócio') ||
        t.includes('founder') || t.includes('co-founder') || t.includes('partner')) {
        return 'c-level';
    }

    // VP
    if (t.includes(' vp ') || t.includes('vice president') || t.includes('vice-president') ||
        t.includes('vp of') || t.includes('vp,')) {
        return 'vp';
    }

    // Director
    if (t.includes('director') || t.includes('diretor') || t.includes('head of') ||
        t.includes('head,') || t.includes(' head ')) {
        return 'director';
    }

    // Manager
    if (t.includes('manager') || t.includes('gerente') || t.includes('lead') ||
        t.includes('líder') || t.includes('lider') || t.includes('coordenador') ||
        t.includes('coordinator') || t.includes('supervisor')) {
        return 'manager';
    }

    // Senior
    if (t.includes('senior') || t.includes('sênior') || t.includes('sr.') ||
        t.includes('sr ') || t.includes('staff') || t.includes('principal') ||
        t.includes('specialist') || t.includes('especialista') || t.includes('pleno')) {
        return 'senior';
    }

    // Junior
    if (t.includes('junior') || t.includes('júnior') || t.includes('jr.') ||
        t.includes('jr ') || t.includes('entry') || t.includes('trainee') ||
        t.includes('associate') || t.includes('assistant') || t.includes('analista')) {
        return 'junior';
    }

    // Intern
    if (t.includes('intern') || t.includes('estagiário') || t.includes('estagiario') ||
        t.includes('estágio') || t.includes('estagio')) {
        return 'intern';
    }

    return 'mid'; // Default
}

/**
 * Full classification from candidate data
 */
function extractSearchableClassificationV2(candidateData: any): {
    function: string;
    level: string;
    title_keywords: string[];
    companies: string[];
    domain: string[];
} {
    const analysis = candidateData.intelligent_analysis || {};

    // Get text from multiple sources
    const currentLevel = analysis?.career_trajectory_analysis?.current_level || '';
    const workHistory = analysis?.work_history || [];
    const experience = candidateData.original_data?.experience || '';

    // Parse experience string for actual roles
    const parsedExperience = extractRoleFromExperience(experience);

    // Combine all role text for classification
    const allRoleText = [
        currentLevel,
        ...(workHistory.map((j: any) => j.role || '').filter(Boolean)),
        ...(parsedExperience.map(j => j.role).filter(Boolean))
    ].join(' ');

    // Classify function using all available text
    const jobFunction = classifyFunction(allRoleText);

    // Classify level - PRIORITIZE actual job title from experience over AI's assessment
    // "Chief Product Officer" from experience is more accurate than "Senior Product Management" from AI
    const actualTitle = parsedExperience[0]?.role || '';
    const levelText = actualTitle || currentLevel || '';
    const level = classifyLevel(levelText);

    // Extract title keywords - prefer parsed experience
    const titleKeywords: string[] = [];
    if (parsedExperience.length > 0) {
        titleKeywords.push(parsedExperience[0].role);
    }
    if (currentLevel && !titleKeywords.includes(currentLevel)) {
        titleKeywords.push(currentLevel);
    }

    // Extract companies from all sources
    const companies: string[] = [];

    // From work_history
    if (workHistory.length > 0) {
        for (const job of workHistory.slice(0, 5)) {
            if (job.company && !companies.includes(job.company)) {
                companies.push(job.company);
            }
        }
    }

    // From parsed experience
    for (const job of parsedExperience.slice(0, 5)) {
        if (job.company && !companies.includes(job.company)) {
            companies.push(job.company);
        }
    }

    // Limit to 5 companies
    const topCompanies = companies.slice(0, 5);

    // Domain detection
    const domain: string[] = [];
    const companyText = topCompanies.join(' ').toLowerCase();

    if (companyText.includes('nubank') || companyText.includes('stone') ||
        companyText.includes('banco') || companyText.includes('fintech') ||
        companyText.includes('creditas') || companyText.includes('inter') ||
        companyText.includes('c6') || companyText.includes('btg') ||
        companyText.includes('pagseguro') || companyText.includes('pagbank')) {
        domain.push('fintech');
    }
    if (companyText.includes('ifood') || companyText.includes('rappi') ||
        companyText.includes('delivery') || companyText.includes('uber eats') ||
        companyText.includes('doordash') || companyText.includes('instacart')) {
        domain.push('delivery');
    }
    if (companyText.includes('mercado') || companyText.includes('amazon') ||
        companyText.includes('magazineluiza') || companyText.includes('magalu') ||
        companyText.includes('b2w') || companyText.includes('americanas') ||
        companyText.includes('vtex') || companyText.includes('shopify')) {
        domain.push('e-commerce');
    }
    if (companyText.includes('google') || companyText.includes('meta') ||
        companyText.includes('facebook') || companyText.includes('microsoft') ||
        companyText.includes('amazon') || companyText.includes('apple') ||
        companyText.includes('netflix') || companyText.includes('spotify')) {
        domain.push('big-tech');
    }
    if (companyText.includes('loft') || companyText.includes('quintoandar') ||
        companyText.includes('quinto andar') || companyText.includes('imovel') ||
        companyText.includes('real estate')) {
        domain.push('proptech');
    }

    return {
        function: jobFunction,
        level,
        title_keywords: titleKeywords.filter(t => t && t.length > 0),
        companies: topCompanies,
        domain
    };
}

/**
 * Backfill v2 - Uses full candidate data including original_data.experience
 */
export const backfillClassifications = onRequest(
    {
        memory: '2GiB',
        timeoutSeconds: 540,
        region: 'us-central1'
    },
    async (req, res) => {
        const batchSize = parseInt(req.query.batchSize as string) || 500;
        const startAfter = req.query.startAfter as string || null;
        const forceUpdate = req.query.force === 'true';

        console.log(`Starting backfill v2 with batchSize=${batchSize}, startAfter=${startAfter}, force=${forceUpdate}`);

        try {
            let query = firestore.collection('candidates')
                .orderBy('__name__')
                .limit(batchSize);

            if (startAfter) {
                const startDoc = await firestore.collection('candidates').doc(startAfter).get();
                if (startDoc.exists) {
                    query = query.startAfter(startDoc);
                }
            }

            const snapshot = await query.get();

            if (snapshot.empty) {
                res.json({
                    success: true,
                    message: 'No more candidates to process',
                    processed: 0
                });
                return;
            }

            console.log(`Processing ${snapshot.docs.length} candidates...`);

            const stats = {
                processed: 0,
                skipped: 0,
                byFunction: {} as Record<string, number>,
                byLevel: {} as Record<string, number>,
                lastDocId: ''
            };

            const batches = [];
            let currentBatch = firestore.batch();
            let batchCount = 0;

            for (const doc of snapshot.docs) {
                const data = doc.data();
                stats.lastDocId = doc.id;

                // Skip if already has searchable and not forcing
                if (!forceUpdate && data.searchable?.function && data.searchable.function !== 'general') {
                    stats.skipped++;
                    continue;
                }

                // Need at least some data to classify
                if (!data.intelligent_analysis && !data.original_data?.experience) {
                    stats.skipped++;
                    continue;
                }

                const searchable = extractSearchableClassificationV2(data);

                currentBatch.update(doc.ref, { searchable });
                batchCount++;
                stats.processed++;

                stats.byFunction[searchable.function] = (stats.byFunction[searchable.function] || 0) + 1;
                stats.byLevel[searchable.level] = (stats.byLevel[searchable.level] || 0) + 1;

                if (batchCount >= 500) {
                    batches.push(currentBatch.commit());
                    currentBatch = firestore.batch();
                    batchCount = 0;
                }
            }

            if (batchCount > 0) {
                batches.push(currentBatch.commit());
            }

            await Promise.all(batches);

            console.log(`Backfill v2 complete. Processed: ${stats.processed}, Skipped: ${stats.skipped}`);
            console.log(`By function:`, stats.byFunction);
            console.log(`By level:`, stats.byLevel);

            res.json({
                success: true,
                version: 'v2',
                processed: stats.processed,
                skipped: stats.skipped,
                byFunction: stats.byFunction,
                byLevel: stats.byLevel,
                lastDocId: stats.lastDocId,
                hasMore: snapshot.docs.length === batchSize,
                nextUrl: snapshot.docs.length === batchSize
                    ? `?batchSize=${batchSize}&startAfter=${stats.lastDocId}${forceUpdate ? '&force=true' : ''}`
                    : null
            });

        } catch (error: any) {
            console.error('Backfill v2 error:', error);
            res.status(500).json({
                success: false,
                error: error.message
            });
        }
    }
);

/**
 * Get classification stats
 */
export const getClassificationStats = onRequest(
    {
        memory: '1GiB',
        timeoutSeconds: 120,
        region: 'us-central1'
    },
    async (req, res) => {
        try {
            const totalSnap = await firestore.collection('candidates').count().get();
            const total = totalSnap.data().count;

            const withSearchableSnap = await firestore.collection('candidates')
                .where('searchable.function', '!=', null)
                .count()
                .get();
            const withSearchable = withSearchableSnap.data().count;

            // Get distribution by function
            const functionCounts: Record<string, number> = {};
            const levelCounts: Record<string, number> = {};

            for (const fn of ['product', 'engineering', 'data', 'design', 'sales', 'marketing', 'hr', 'finance', 'operations', 'general']) {
                const snap = await firestore.collection('candidates')
                    .where('searchable.function', '==', fn)
                    .count()
                    .get();
                functionCounts[fn] = snap.data().count;
            }

            for (const lv of ['c-level', 'vp', 'director', 'manager', 'senior', 'mid', 'junior', 'intern']) {
                const snap = await firestore.collection('candidates')
                    .where('searchable.level', '==', lv)
                    .count()
                    .get();
                levelCounts[lv] = snap.data().count;
            }

            res.json({
                total,
                withSearchable,
                percentClassified: Math.round((withSearchable / total) * 100),
                functionDistribution: functionCounts,
                levelDistribution: levelCounts
            });

        } catch (error: any) {
            console.error('Stats error:', error);
            res.status(500).json({
                success: false,
                error: error.message
            });
        }
    }
);
