#!/bin/bash
# Test runner script for the Crawler project

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="unit"
COVERAGE=true
VERBOSE=false
PARALLEL=false
FAIL_FAST=false
HTML_REPORT=false

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE       Test type: unit, integration, all (default: unit)"
    echo "  -c, --no-coverage     Disable coverage reporting"
    echo "  -v, --verbose         Verbose output"
    echo "  -p, --parallel        Run tests in parallel"
    echo "  -f, --fail-fast       Stop on first failure"
    echo "  -h, --html-report     Generate HTML coverage report"
    echo "  --help                Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    Run unit tests with coverage"
    echo "  $0 -t integration     Run integration tests"
    echo "  $0 -t all -p          Run all tests in parallel"
    echo "  $0 -v -h              Run with verbose output and HTML report"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -c|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -f|--fail-fast)
            FAIL_FAST=true
            shift
            ;;
        -h|--html-report)
            HTML_REPORT=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate test type
case $TEST_TYPE in
    unit|integration|all)
        ;;
    *)
        print_error "Invalid test type: $TEST_TYPE"
        print_error "Valid types: unit, integration, all"
        exit 1
        ;;
esac

# Change to project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

print_status "Running tests from: $PROJECT_ROOT"
print_status "Test type: $TEST_TYPE"

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    print_error "pytest is not installed or not in PATH"
    print_error "Please install it with: pip install pytest"
    exit 1
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add test type markers
case $TEST_TYPE in
    unit)
        PYTEST_CMD="$PYTEST_CMD -m 'unit or not (integration or slow)'"
        ;;
    integration)
        PYTEST_CMD="$PYTEST_CMD -m integration"
        ;;
    all)
        # Run all tests
        ;;
esac

# Add coverage options
if [ "$COVERAGE" = true ]; then
    print_status "Coverage reporting enabled"
    if [ "$HTML_REPORT" = true ]; then
        print_status "HTML coverage report will be generated"
    fi
else
    PYTEST_CMD="$PYTEST_CMD --no-cov"
    print_status "Coverage reporting disabled"
fi

# Add verbose option
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
    print_status "Verbose output enabled"
fi

# Add parallel option
if [ "$PARALLEL" = true ]; then
    # Check if pytest-xdist is available
    if python -c "import xdist" 2>/dev/null; then
        PYTEST_CMD="$PYTEST_CMD -n auto"
        print_status "Parallel execution enabled"
    else
        print_warning "pytest-xdist not available, running sequentially"
        print_warning "Install with: pip install pytest-xdist"
    fi
fi

# Add fail-fast option
if [ "$FAIL_FAST" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -x"
    print_status "Fail-fast enabled"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Run tests
print_status "Executing: $PYTEST_CMD"
echo ""

if eval $PYTEST_CMD; then
    print_success "All tests passed!"
    
    # Show coverage report location if generated
    if [ "$COVERAGE" = true ] && [ "$HTML_REPORT" = true ]; then
        if [ -d "coverage_html" ]; then
            print_status "HTML coverage report available at: coverage_html/index.html"
        fi
    fi
    
    exit 0
else
    EXIT_CODE=$?
    print_error "Tests failed with exit code: $EXIT_CODE"
    exit $EXIT_CODE
fi