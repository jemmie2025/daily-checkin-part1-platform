import http from 'k6/http';
import { check } from 'k6';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {checks: ['rate==1']},
};

export default function () {
  const target = __ENV.CHECKIN_OPEN_URL;
  if (!target?.startsWith('https://')) throw new Error('CHECKIN_OPEN_URL must use HTTPS');
  const userId = `rate-limit-${Date.now()}`;
  const common = {
    token: __ENV.CHECKIN_TEST_COMMAND_TOKEN,
    trigger_id: 'isolated-control-test',
    user_id: userId,
    user_name: userId,
    channel_id: __ENV.CHECKIN_TEST_CHANNEL_ID,
    team_id: __ENV.CHECKIN_TEST_TEAM_ID,
    command: '/ci',
    text: '',
  };
  const responses = [];
  for (let request = 1; request <= 11; request += 1) responses.push(http.post(target, common));
  check(responses, {
    'first ten requests pass gateway quota': (items) => items.slice(0, 10).every((item) => item.status === 200),
    'eleventh request is throttled': (items) => items[10].status === 429,
  });

  const oversized = 'x'.repeat(65537);
  const bodyResponse = http.post(target, oversized, {headers: {'Content-Type': 'application/octet-stream'}});
  check(bodyResponse, {'65,537-byte request is rejected': (result) => [400, 413].includes(result.status)});

  const methodResponse = http.get(target);
  check(methodResponse, {'GET is rejected': (result) => [404, 405].includes(result.status)});
}
