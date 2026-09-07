import http from 'k6/http';
import { check } from 'k6';

const target = __ENV.CHECKIN_OPEN_URL;
const commandToken = __ENV.CHECKIN_TEST_COMMAND_TOKEN;

export const options = {
  scenarios: {
    open_latency: {
      executor: 'constant-arrival-rate',
      rate: 5,
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 20,
      maxVUs: 60,
      tags: { test: 'open_latency' },
    },
  },
  thresholds: {
    'http_req_duration{test:open_latency}': ['p(95)<1800', 'p(99)<1950'],
    'http_req_failed{test:open_latency}': ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export function setup() {
  if (!target?.startsWith('https://')) throw new Error('CHECKIN_OPEN_URL must use HTTPS');
  if (!commandToken) throw new Error('CHECKIN_TEST_COMMAND_TOKEN is required');
}

export default function () {
  const uniqueUser = `load-${__VU}-${__ITER}`;
  const body = {
    token: commandToken,
    trigger_id: `staging-trigger-${__VU}-${__ITER}`,
    user_id: uniqueUser,
    user_name: uniqueUser,
    channel_id: __ENV.CHECKIN_TEST_CHANNEL_ID,
    team_id: __ENV.CHECKIN_TEST_TEAM_ID,
    command: '/ci',
    text: '',
  };
  const response = http.post(target, body, {
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    tags: {test: 'open_latency'},
    timeout: '2s',
  });
  check(response, {
    'open returns 200': (result) => result.status === 200,
    'open returns empty JSON': (result) => result.body.trim() === '{}',
    'open stays under two seconds': (result) => result.timings.duration < 2000,
  });
}
