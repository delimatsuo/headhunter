const {onRequest} = require("firebase-functions/v2/https");
const {logger} = require("firebase-functions");
const admin = require("firebase-admin");
const cors = require("cors")({origin: true});

// Initialize Firebase Admin
admin.initializeApp();

// Health check endpoint
exports.healthCheck = onRequest((request, response) => {
  cors(request, response, () => {
    response.json({
      status: "healthy",
      timestamp: new Date().toISOString(),
      services: {
        firestore: "connected",
        storage: "connected",
        vertexAI: "available"
      }
    });
  });
});

// Placeholder for candidate processing function
exports.processCandidate = onRequest((request, response) => {
  cors(request, response, async () => {
    try {
      if (request.method !== "POST") {
        response.status(405).json({error: "Method not allowed"});
        return;
      }

      const {candidateData} = request.body;
      
      if (!candidateData) {
        response.status(400).json({error: "Candidate data is required"});
        return;
      }

      logger.info("Processing candidate:", candidateData.candidate_id);

      // TODO: Implement Vertex AI processing
      // This will be implemented in future tasks
      
      response.json({
        message: "Candidate processing endpoint ready",
        candidateId: candidateData.candidate_id,
        status: "placeholder"
      });

    } catch (error) {
      logger.error("Error processing candidate:", error);
      response.status(500).json({error: "Internal server error"});
    }
  });
});

// Placeholder for search function
exports.searchCandidates = onRequest((request, response) => {
  cors(request, response, async () => {
    try {
      if (request.method !== "POST") {
        response.status(405).json({error: "Method not allowed"});
        return;
      }

      const {jobDescription, limit = 10} = request.body;
      
      if (!jobDescription) {
        response.status(400).json({error: "Job description is required"});
        return;
      }

      logger.info("Searching candidates for job description");

      // TODO: Implement Vector Search
      // This will be implemented in future tasks
      
      response.json({
        message: "Candidate search endpoint ready",
        jobDescription: jobDescription.substring(0, 100) + "...",
        limit: limit,
        status: "placeholder"
      });

    } catch (error) {
      logger.error("Error searching candidates:", error);
      response.status(500).json({error: "Internal server error"});
    }
  });
});