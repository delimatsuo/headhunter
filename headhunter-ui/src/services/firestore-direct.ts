import {
  collection,
  query,
  getDocs,
  getCountFromServer,
  limit,
  orderBy,
  where,
  DocumentData,
  QueryConstraint
} from 'firebase/firestore';
import { db } from '../config/firebase';
import { CandidateProfile, DashboardStats } from '../types';

export const firestoreService = {
  // Get candidates directly from Firestore
  async getCandidatesDirect(maxResults: number = 100, orgId?: string): Promise<CandidateProfile[]> {
    try {
      console.log('Firestore getCandidatesDirect called with orgId:', orgId, 'maxResults:', maxResults);
      const candidatesRef = collection(db, 'candidates');
      const constraints: QueryConstraint[] = [];

      // Filter by org_id if provided (required for multi-tenant access)
      if (orgId) {
        constraints.push(where('org_id', '==', orgId));
        // Note: Avoiding orderBy with where clause to prevent composite index requirement
        // Client-side sorting will be done instead
      } else {
        // If no org_id, use original ordering (may fetch all candidates)
        constraints.push(orderBy('processing_metadata.timestamp', 'desc'));
      }

      constraints.push(limit(maxResults));

      const q = query(candidatesRef, ...constraints);
      console.log('Executing Firestore query for candidates...');
      const snapshot = await getDocs(q);
      console.log('Firestore query returned', snapshot.size, 'candidates');

      const candidates: CandidateProfile[] = [];
      snapshot.forEach((doc) => {
        const data = doc.data();
        // Log data for debugging
        console.log('Candidate Data:', data);
        candidates.push({
          id: doc.id,
          name: (data.name && data.name !== 'Unknown Candidate' && data.name !== 'Unknown')
            ? data.name
            : (data.documents?.resume_ref?.split('/').pop() || 'Unknown Candidate'),
          title: data.current_role || data.ai_analysis?.experience_analysis?.current_role || 'Not specified',
          company: data.ai_analysis?.experience_analysis?.companies?.[0] || 'Unknown',
          location: data.ai_analysis?.personal_details?.location || 'Not specified',
          skills: data.primary_skills || data.ai_analysis?.technical_assessment?.primary_skills || [],
          experience: data.years_experience || data.ai_analysis?.personal_details?.years_of_experience || '0',
          education: data.ai_analysis?.education_analysis?.degrees?.join(', ') || 'Not specified',
          summary: data.ai_analysis?.executive_summary?.one_line_pitch || 'No summary available',
          matchScore: parseFloat(data.overall_rating === 'A' ? '0.9' :
            data.overall_rating === 'B' ? '0.7' :
              data.overall_rating === 'C' ? '0.5' : '0.3'),
          overall_score: parseFloat(data.overall_rating === 'A' ? '0.9' :
            data.overall_rating === 'B' ? '0.7' :
              data.overall_rating === 'C' ? '0.5' : '0.3'),
          strengths: data.ai_analysis?.recruiter_recommendations?.strengths || [],
          fitReasons: [],
          availability: 'Unknown',
          desiredSalary: data.ai_analysis?.market_insights?.estimated_salary_range || 'Not specified',
          profileUrl: '#',
          lastUpdated: data.processing_metadata?.timestamp || new Date().toISOString()
        });
      });

      return candidates;
    } catch (error) {
      console.error('Error fetching candidates from Firestore:', error);
      return [];
    }
  },

  // Get dashboard statistics
  async getDashboardStats(orgId?: string): Promise<DashboardStats> {
    try {
      console.log('Firestore getDashboardStats called with orgId:', orgId);
      const candidatesRef = collection(db, 'candidates');

      // Build base query with org_id filter
      let baseQuery;
      if (orgId) {
        baseQuery = query(candidatesRef, where('org_id', '==', orgId));
      } else {
        baseQuery = query(candidatesRef);
      }

      // Use count aggregation for total (much faster than loading all docs)
      console.log('Executing Firestore count query...');
      const countSnapshot = await getCountFromServer(baseQuery);
      const totalCandidates = countSnapshot.data().count;
      console.log('Total candidates:', totalCandidates);

      // For detailed stats, only sample first 500 docs (fast)
      const sampleQuery = query(baseQuery, limit(500));
      const sampleSnapshot = await getDocs(sampleQuery);

      let totalMatchScore = 0;
      let highMatches = 0;
      const skillsMap = new Map<string, number>();
      const companiesMap = new Map<string, number>();

      sampleSnapshot.forEach((doc) => {
        const data = doc.data();

        // Calculate match scores
        const rating = data.overall_rating || 'D';
        const score = rating === 'A' ? 0.9 : rating === 'B' ? 0.7 : rating === 'C' ? 0.5 : 0.3;
        totalMatchScore += score;
        if (score >= 0.7) highMatches++;

        // Count skills
        const skills = data.primary_skills || data.ai_analysis?.technical_assessment?.primary_skills || [];
        skills.forEach((skill: string) => {
          skillsMap.set(skill, (skillsMap.get(skill) || 0) + 1);
        });

        // Count companies
        const companies = data.ai_analysis?.experience_analysis?.companies || [];
        companies.forEach((company: string) => {
          companiesMap.set(company, (companiesMap.get(company) || 0) + 1);
        });
      });

      const avgMatchScore = sampleSnapshot.size > 0 ? totalMatchScore / sampleSnapshot.size : 0;

      // Get top skills
      const topSkills = Array.from(skillsMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([skill, count]) => ({ skill, count }));

      // Get top companies  
      const topCompanies = Array.from(companiesMap.entries())
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([company, count]) => ({ company, count }));

      return {
        totalCandidates,
        activeSearches: 1, // We have 1 active processing job
        avgMatchScore: Math.round(avgMatchScore * 100) / 100,
        recentActivity: {
          searches: 1,
          newCandidates: totalCandidates,
          highMatches
        },
        topSkills,
        topCompanies
      };
    } catch (error) {
      console.error('Error fetching dashboard stats:', error);
      return null as any;
    }
  },

  // Quick Find: search by name, company, or title (keyword-based)
  async quickFindCandidates(
    searchQuery: string,
    orgId?: string,
    maxResults: number = 50
  ): Promise<CandidateProfile[]> {
    try {
      console.log('Quick Find search:', searchQuery, 'orgId:', orgId);
      const candidatesRef = collection(db, 'candidates');

      // Firestore has 10k limit per query, so we need to batch
      // For Quick Find, we'll search through all candidates in chunks
      const allDocs: any[] = [];
      let lastDoc = null;
      const batchSize = 10000;
      const maxBatches = 3; // Up to 30k candidates

      for (let batch = 0; batch < maxBatches; batch++) {
        let q;
        // Ella org (org_ella_main) sees ALL candidates regardless of org
        // This is a security policy exception for the main recruiting agency
        const isEllaOrg = orgId === 'org_ella_main';

        if (orgId && !isEllaOrg) {
          // Non-Ella orgs filter by org_id
          if (lastDoc) {
            q = query(candidatesRef, where('org_id', '==', orgId), limit(batchSize));
          } else {
            q = query(candidatesRef, where('org_id', '==', orgId), limit(batchSize));
          }
        } else {
          // Ella org OR no org restriction: search all candidates
          q = query(candidatesRef, limit(batchSize));
        }

        const snapshot = await getDocs(q);
        if (snapshot.empty) break;

        snapshot.docs.forEach(doc => allDocs.push(doc));

        // For simplicity, break after first batch for now (10k is usually enough)
        // TODO: Implement proper pagination with startAfter for full search
        break;
      }

      console.log('Quick Find: fetched', allDocs.length, 'candidates to search');

      const searchTerms = searchQuery.toLowerCase().trim().split(/\s+/);
      const candidates: CandidateProfile[] = [];

      allDocs.forEach((doc) => {
        const data = doc.data();

        // Build searchable text from key fields
        const name = (data.name || '').toLowerCase();
        const company = (data.current_company || data.ai_analysis?.experience_analysis?.companies?.[0] || '').toLowerCase();
        const title = (data.current_role || data.ai_analysis?.experience_analysis?.current_role || '').toLowerCase();
        const skills = (data.primary_skills || []).join(' ').toLowerCase();

        // Check if ALL search terms match (AND logic)
        const matchesAll = searchTerms.every(term =>
          name.includes(term) ||
          company.includes(term) ||
          title.includes(term) ||
          skills.includes(term)
        );

        if (matchesAll) {
          candidates.push({
            id: doc.id,
            name: data.name || 'Unknown',
            title: data.current_role || data.ai_analysis?.experience_analysis?.current_role || 'Not specified',
            company: data.current_company || data.ai_analysis?.experience_analysis?.companies?.[0] || 'Unknown',
            location: data.ai_analysis?.personal_details?.location || 'Not specified',
            skills: data.primary_skills || data.ai_analysis?.technical_assessment?.primary_skills || [],
            experience: data.years_experience || data.ai_analysis?.personal_details?.years_of_experience || '0',
            education: data.ai_analysis?.education_analysis?.degrees?.join(', ') || 'Not specified',
            summary: data.ai_analysis?.executive_summary?.one_line_pitch || 'No summary available',
            matchScore: 1, // For keyword matches, score is 1
            overall_score: 1,
            strengths: data.ai_analysis?.recruiter_recommendations?.strengths || [],
            fitReasons: [],
            availability: 'Unknown',
            desiredSalary: data.ai_analysis?.market_insights?.estimated_salary_range || 'Not specified',
            profileUrl: '#',
            lastUpdated: data.processing_metadata?.timestamp || new Date().toISOString()
          });
        }
      });

      console.log('Quick Find: matched', candidates.length, 'candidates');
      return candidates.slice(0, maxResults);
    } catch (error) {
      console.error('Error in quickFindCandidates:', error);
      return [];
    }
  },

  // Legacy search (kept for backwards compatibility)
  async searchCandidates(searchQuery: string, maxResults: number = 20): Promise<CandidateProfile[]> {
    return this.quickFindCandidates(searchQuery, undefined, maxResults);
  }
};