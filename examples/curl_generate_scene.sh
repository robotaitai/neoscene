#!/bin/bash
# Example: Generate a scene using the Neoscene API
#
# Prerequisites:
#   1. Start the API server: python -m neoscene.app.main --api
#   2. Run this script from the project root

set -e

API_URL="${NEOSCENE_API_URL:-http://localhost:8000}"

echo "=== Neoscene API Examples ==="
echo "API URL: $API_URL"
echo ""

# Health check
echo "1. Health Check"
echo "   GET /health"
curl -s "$API_URL/health" | python3 -m json.tool
echo ""

# List assets
echo "2. List Assets"
echo "   GET /assets"
curl -s "$API_URL/assets" | python3 -m json.tool
echo ""

# Search assets
echo "3. Search Assets"
echo "   POST /assets/search"
curl -s -X POST "$API_URL/assets/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "tractor", "category": "robot"}' | python3 -m json.tool
echo ""

# Generate scene
echo "4. Generate Scene"
echo "   POST /generate_scene"
echo "   Prompt: 'A small orchard with a red tractor and 5 wooden crates'"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/generate_scene" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A small orchard with a red tractor and 5 wooden crates arranged in a line",
    "include_mjcf": true
  }')

echo "Response (scene_spec only):"
echo "$RESPONSE" | python3 -c "import sys, json; data = json.load(sys.stdin); print(json.dumps(data.get('scene_spec', {}), indent=2))"

echo ""
echo "=== Done ==="
echo ""
echo "To save the MJCF XML, use:"
echo "  curl -s -X POST $API_URL/generate_scene -H 'Content-Type: application/json' -d '{\"prompt\": \"...\"}' | jq -r '.mjcf_xml' > scene.xml"

