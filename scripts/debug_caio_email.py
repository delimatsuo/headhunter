import csv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    filepath = "CSV files/505039_Ella_Executive_Search_CSVs_1/Ella_Executive_Search_candidates_1-1.csv"
    target_id = "190084523"
    
    logger.info(f"Searching for {target_id} in {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            if row and row[0] == target_id:
                logger.info("🎯 Found Caio Maia!")
                logger.info(f"Row length: {len(row)}")
                for i, col in enumerate(row):
                    logger.info(f"Col {i}: {col}")
                return

    logger.warning("❌ Caio Maia not found in file.")

if __name__ == "__main__":
    main()
